"""Hash-chained, append-only audit ledger.

The span table it replaces is a mutable SQLite table with an unconditional
90-day prune. That is a log, and a log is not evidence: anyone with write
access can rewrite a routing decision after the fact and nothing detects it.

Each entry commits to its predecessor:

    entry_hash = SHA256(workspace | chain_seq | prev_hash | payload_hash)

Changing or removing any entry breaks every hash after it, and `verify()`
reports the first position where the chain stops agreeing with itself. The
chain is per workspace, so one tenant's write volume never delays another's,
and a tenant can be handed a verifiable extract of only its own history.

This does not defend against an attacker who rewrites the whole chain --
nothing local can. It makes tampering *detectable*, and combined with
periodically exporting the head hash somewhere the database cannot reach, it
becomes hard to hide. `head()` exists for exactly that.

Postgres in production, SQLite for tests and single-node installs. The chain
logic is identical; only the locking differs.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
    text,
)

GENESIS_HASH = "0" * 64
DEFAULT_RETENTION_DAYS = 90

metadata = MetaData()

audit_entries = Table(
    "audit_entries",
    metadata,
    # SQLite only autoincrements a column declared exactly INTEGER PRIMARY KEY,
    # so BIGINT would insert NULL and fail the NOT NULL constraint.
    Column(
        "seq",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("workspace_id", String(128), nullable=False, index=True),
    # Position within this workspace's chain. Unique per workspace, so a gap
    # is itself evidence of a deletion.
    Column("chain_seq", BigInteger, nullable=False),
    Column("entry_type", String(32), nullable=False),
    Column("recorded_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("payload", Text, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("prev_hash", String(64), nullable=False),
    Column("entry_hash", String(64), nullable=False, unique=True),
)

# One row per workspace. Serialises appends and survives pruning, so the chain
# stays verifiable after its early entries are gone.
chain_heads = Table(
    "audit_chain_heads",
    metadata,
    Column("workspace_id", String(128), primary_key=True),
    Column("head_hash", String(64), nullable=False, default=GENESIS_HASH),
    Column("chain_seq", BigInteger, nullable=False, default=0),
    # Where verification may legitimately start. Pruning moves this forward so
    # a truncated prefix is not mistaken for tampering.
    Column("pruned_through_seq", BigInteger, nullable=False, default=0),
    Column("pruned_through_hash", String(64), nullable=False, default=GENESIS_HASH),
)

retention_policies = Table(
    "audit_retention",
    metadata,
    Column("workspace_id", String(128), primary_key=True),
    Column("retention_days", Integer, nullable=True),
    # Suspends deletion entirely. A retention job that silently destroys
    # evidence during a dispute is worse than no retention job.
    Column("legal_hold", Boolean, nullable=False, default=False),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)


def canonical(payload: Dict[str, Any]) -> str:
    """Byte-stable JSON. Key order must not change a hash."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def compute_entry_hash(
    workspace_id: str, chain_seq: int, prev_hash: str, payload_hash: str
) -> str:
    material = f"{workspace_id}|{chain_seq}|{prev_hash}|{payload_hash}"
    return hashlib.sha256(material.encode()).hexdigest()


def _normalise_url(url: str) -> str:
    # SQLAlchemy 2 dropped the bare `postgres://` alias that many hosted
    # providers still hand out.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class AuditLedger:
    def __init__(self, database_url: Optional[str] = None):
        url = database_url or os.environ.get("AUDIT_LEDGER_URL") or os.environ.get(
            "DATABASE_URL"
        )
        if not url:
            path = os.environ.get("TRACER_DB_PATH", "./data/sentinel.db")
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            url = f"sqlite:///{path}"
        self.url = _normalise_url(url)
        self.is_postgres = self.url.startswith("postgresql")
        self.engine = create_engine(
            self.url,
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if not self.is_postgres else {},
        )
        # SQLite has no row-level locking, so appends are serialised here.
        # Postgres uses SELECT ... FOR UPDATE on the head row instead, which
        # holds across processes as well as threads.
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_ws_seq "
                    "ON audit_entries (workspace_id, chain_seq)"
                )
            )
            if self.is_postgres:
                self._install_append_only_guard(conn)

    def _install_append_only_guard(self, conn):
        """Refuse UPDATE at the database level.

        Application-level append-only is a convention. A rule the database
        enforces survives someone reaching for psql, which is the case the
        ledger exists for. DELETE stays permitted because retention needs it,
        and pruning advances the watermark so truncation is distinguishable
        from tampering.
        """
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION kubemind_audit_no_update()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION
                        'audit_entries is append-only; entry % cannot be modified',
                        OLD.seq;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        conn.execute(text("DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_entries"))
        conn.execute(
            text(
                "CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_entries "
                "FOR EACH ROW EXECUTE FUNCTION kubemind_audit_no_update()"
            )
        )

    # ── Append ───────────────────────────────────────────────────

    def append(
        self,
        workspace_id: str,
        payload: Dict[str, Any],
        entry_type: str = "span",
    ) -> Dict[str, Any]:
        """Append one entry and return its chain position and hash."""
        workspace_id = workspace_id or "default"
        payload_hash = hash_payload(payload)
        body = canonical(payload)

        with self._lock:
            with self.engine.begin() as conn:
                head = self._lock_head(conn, workspace_id)
                chain_seq = head["chain_seq"] + 1
                prev_hash = head["head_hash"]
                entry_hash = compute_entry_hash(
                    workspace_id, chain_seq, prev_hash, payload_hash
                )
                recorded_at = datetime.utcnow()

                conn.execute(
                    audit_entries.insert().values(
                        workspace_id=workspace_id,
                        chain_seq=chain_seq,
                        entry_type=entry_type,
                        recorded_at=recorded_at,
                        payload=body,
                        payload_hash=payload_hash,
                        prev_hash=prev_hash,
                        entry_hash=entry_hash,
                    )
                )
                conn.execute(
                    chain_heads.update()
                    .where(chain_heads.c.workspace_id == workspace_id)
                    .values(head_hash=entry_hash, chain_seq=chain_seq)
                )

        return {
            "workspace_id": workspace_id,
            "chain_seq": chain_seq,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "payload_hash": payload_hash,
            "recorded_at": recorded_at.isoformat(),
        }

    def _lock_head(self, conn, workspace_id: str) -> Dict[str, Any]:
        stmt = select(chain_heads).where(chain_heads.c.workspace_id == workspace_id)
        if self.is_postgres:
            stmt = stmt.with_for_update()
        row = conn.execute(stmt).mappings().first()
        if row:
            return dict(row)

        conn.execute(
            chain_heads.insert().values(
                workspace_id=workspace_id,
                head_hash=GENESIS_HASH,
                chain_seq=0,
                pruned_through_seq=0,
                pruned_through_hash=GENESIS_HASH,
            )
        )
        return {
            "workspace_id": workspace_id,
            "head_hash": GENESIS_HASH,
            "chain_seq": 0,
            "pruned_through_seq": 0,
            "pruned_through_hash": GENESIS_HASH,
        }

    # ── Verify ───────────────────────────────────────────────────

    def verify(self, workspace_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Walk the chain and report the first position that disagrees.

        Three independent things are checked, because they fail differently:
        a rewritten payload breaks `payload_hash`, a forged link breaks
        `prev_hash`, and a deleted entry leaves a gap in `chain_seq`.
        """
        with self.engine.begin() as conn:
            head = conn.execute(
                select(chain_heads).where(chain_heads.c.workspace_id == workspace_id)
            ).mappings().first()

            stmt = (
                select(audit_entries)
                .where(audit_entries.c.workspace_id == workspace_id)
                .order_by(audit_entries.c.chain_seq)
            )
            if limit:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).mappings().all()

        if not rows:
            return {
                "workspace_id": workspace_id,
                "valid": True,
                "entries_checked": 0,
                "head_hash": (head or {}).get("head_hash", GENESIS_HASH),
                "detail": "empty chain",
            }

        # Pruning legitimately removes a prefix, so the walk starts from the
        # watermark rather than from genesis.
        expected_prev = (head or {}).get("pruned_through_hash", GENESIS_HASH)
        expected_seq = (head or {}).get("pruned_through_seq", 0) + 1

        for row in rows:
            if row["chain_seq"] != expected_seq:
                return self._broken(
                    workspace_id,
                    row,
                    f"missing entries: expected chain_seq {expected_seq}, "
                    f"found {row['chain_seq']}",
                )
            if hash_payload(json.loads(row["payload"])) != row["payload_hash"]:
                return self._broken(workspace_id, row, "payload does not match its hash")
            if row["prev_hash"] != expected_prev:
                return self._broken(
                    workspace_id, row, "prev_hash does not match the preceding entry"
                )
            recomputed = compute_entry_hash(
                workspace_id, row["chain_seq"], row["prev_hash"], row["payload_hash"]
            )
            if recomputed != row["entry_hash"]:
                return self._broken(workspace_id, row, "entry_hash is not reproducible")

            expected_prev = row["entry_hash"]
            expected_seq += 1

        stored_head = (head or {}).get("head_hash", GENESIS_HASH)
        if not limit and stored_head != expected_prev:
            return {
                "workspace_id": workspace_id,
                "valid": False,
                "entries_checked": len(rows),
                "broken_at": None,
                "detail": (
                    "chain head does not match the last entry; entries may have "
                    "been removed from the end"
                ),
                "head_hash": stored_head,
                "computed_head": expected_prev,
            }

        return {
            "workspace_id": workspace_id,
            "valid": True,
            "entries_checked": len(rows),
            "first_seq": rows[0]["chain_seq"],
            "last_seq": rows[-1]["chain_seq"],
            "head_hash": expected_prev,
            "verified_at": datetime.utcnow().isoformat(),
        }

    def _broken(self, workspace_id: str, row, detail: str) -> Dict[str, Any]:
        return {
            "workspace_id": workspace_id,
            "valid": False,
            "broken_at": {
                "chain_seq": row["chain_seq"],
                "entry_hash": row["entry_hash"],
                "recorded_at": str(row["recorded_at"]),
            },
            "detail": detail,
            "verified_at": datetime.utcnow().isoformat(),
        }

    def head(self, workspace_id: str) -> Dict[str, Any]:
        """Current head hash.

        Publish this somewhere the database cannot reach and the chain becomes
        anchored: a rewrite that reaches all the way back to genesis still has
        to explain a head hash that no longer matches.
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(chain_heads).where(chain_heads.c.workspace_id == workspace_id)
            ).mappings().first()
        if not row:
            return {
                "workspace_id": workspace_id,
                "head_hash": GENESIS_HASH,
                "chain_seq": 0,
            }
        return {
            "workspace_id": workspace_id,
            "head_hash": row["head_hash"],
            "chain_seq": row["chain_seq"],
            "pruned_through_seq": row["pruned_through_seq"],
        }

    # ── Read ─────────────────────────────────────────────────────

    def entries(
        self,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
        entry_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(audit_entries).where(
            audit_entries.c.workspace_id == workspace_id
        )
        if entry_type:
            stmt = stmt.where(audit_entries.c.entry_type == entry_type)
        stmt = stmt.order_by(audit_entries.c.chain_seq.desc()).limit(limit).offset(offset)

        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()

        out = []
        for row in rows:
            d = dict(row)
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
            d["recorded_at"] = str(d["recorded_at"])
            out.append(d)
        return out

    # ── Retention ────────────────────────────────────────────────

    def set_retention(
        self,
        workspace_id: str,
        retention_days: Optional[int] = None,
        legal_hold: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(retention_policies).where(
                    retention_policies.c.workspace_id == workspace_id
                )
            ).mappings().first()

            values = {"updated_at": datetime.utcnow()}
            if retention_days is not None:
                values["retention_days"] = retention_days
            if legal_hold is not None:
                values["legal_hold"] = legal_hold

            if existing:
                conn.execute(
                    retention_policies.update()
                    .where(retention_policies.c.workspace_id == workspace_id)
                    .values(**values)
                )
            else:
                conn.execute(
                    retention_policies.insert().values(
                        workspace_id=workspace_id,
                        retention_days=retention_days,
                        legal_hold=bool(legal_hold),
                        updated_at=datetime.utcnow(),
                    )
                )
        return self.get_retention(workspace_id)

    def get_retention(self, workspace_id: str) -> Dict[str, Any]:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(retention_policies).where(
                    retention_policies.c.workspace_id == workspace_id
                )
            ).mappings().first()
        if not row:
            return {
                "workspace_id": workspace_id,
                "retention_days": DEFAULT_RETENTION_DAYS,
                "legal_hold": False,
                "source": "default",
            }
        return {
            "workspace_id": workspace_id,
            "retention_days": (
                row["retention_days"]
                if row["retention_days"] is not None
                else DEFAULT_RETENTION_DAYS
            ),
            "legal_hold": bool(row["legal_hold"]),
            "source": "configured",
        }

    def prune(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete entries past their workspace's retention.

        Replaces the unconditional 90-day DELETE. Two differences matter: each
        workspace gets its own window, and a legal hold suspends deletion
        entirely rather than being a comment in a runbook.

        Pruning advances the watermark so the remaining chain still verifies.
        """
        with self.engine.begin() as conn:
            workspaces = (
                [workspace_id]
                if workspace_id
                else [
                    r[0]
                    for r in conn.execute(
                        select(chain_heads.c.workspace_id)
                    ).all()
                ]
            )

        results = {}
        for ws in workspaces:
            policy = self.get_retention(ws)
            if policy["legal_hold"]:
                results[ws] = {"deleted": 0, "skipped": "legal_hold"}
                continue

            cutoff = datetime.utcnow() - timedelta(days=policy["retention_days"])
            with self._lock:
                with self.engine.begin() as conn:
                    last = conn.execute(
                        select(audit_entries)
                        .where(
                            audit_entries.c.workspace_id == ws,
                            audit_entries.c.recorded_at < cutoff,
                        )
                        .order_by(audit_entries.c.chain_seq.desc())
                        .limit(1)
                    ).mappings().first()

                    if not last:
                        results[ws] = {"deleted": 0}
                        continue

                    deleted = conn.execute(
                        audit_entries.delete().where(
                            audit_entries.c.workspace_id == ws,
                            audit_entries.c.chain_seq <= last["chain_seq"],
                        )
                    ).rowcount

                    # Without this the next verify() would read the truncation
                    # as a missing entry and report tampering.
                    conn.execute(
                        chain_heads.update()
                        .where(chain_heads.c.workspace_id == ws)
                        .values(
                            pruned_through_seq=last["chain_seq"],
                            pruned_through_hash=last["entry_hash"],
                        )
                    )
            results[ws] = {
                "deleted": deleted,
                "pruned_through_seq": last["chain_seq"],
                "retention_days": policy["retention_days"],
            }

        return {"pruned": results, "pruned_at": datetime.utcnow().isoformat()}

    def stats(self) -> Dict[str, Any]:
        with self.engine.begin() as conn:
            total = conn.execute(
                select(func.count()).select_from(audit_entries)
            ).scalar_one()
            workspaces = conn.execute(
                select(func.count()).select_from(chain_heads)
            ).scalar_one()
            holds = conn.execute(
                select(func.count())
                .select_from(retention_policies)
                .where(retention_policies.c.legal_hold.is_(True))
            ).scalar_one()
        return {
            "total_entries": total,
            "workspaces": workspaces,
            "legal_holds": holds,
            "backend": "postgres" if self.is_postgres else "sqlite",
        }

    def close(self):
        self.engine.dispose()
