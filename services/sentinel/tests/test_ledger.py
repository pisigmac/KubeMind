"""Hash-chained audit ledger.

The value of this component is entirely in what it *detects*, so most of these
tests tamper with the database directly and assert that verification notices.
A ledger that only passes happy-path tests has not been tested at all.
"""

import json
import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from sentinel.ledger import (
    GENESIS_HASH,
    AuditLedger,
    canonical,
    compute_entry_hash,
    hash_payload,
)


@pytest.fixture
def ledger(tmp_path):
    lg = AuditLedger(f"sqlite:///{tmp_path}/ledger.db")
    yield lg
    lg.close()


def _span(n: int, workspace: str = "acme"):
    return {
        "trace_id": f"t{n}",
        "span_id": f"s{n}",
        "workspace_id": workspace,
        "service": "router",
        "operation": "llm_call",
        "attributes": {"intent": "code", "provider": "ollama", "n": n},
    }


class TestCanonicalisation:
    def test_key_order_does_not_change_the_hash(self):
        assert hash_payload({"a": 1, "b": 2}) == hash_payload({"b": 2, "a": 1})

    def test_different_content_changes_the_hash(self):
        assert hash_payload({"a": 1}) != hash_payload({"a": 2})

    def test_nested_order_is_also_stable(self):
        assert hash_payload({"x": {"a": 1, "b": 2}}) == hash_payload(
            {"x": {"b": 2, "a": 1}}
        )

    def test_canonical_json_has_no_incidental_whitespace(self):
        assert canonical({"a": 1, "b": 2}) == '{"a":1,"b":2}'


class TestAppend:
    def test_first_entry_links_to_genesis(self, ledger):
        entry = ledger.append("acme", _span(1))
        assert entry["prev_hash"] == GENESIS_HASH
        assert entry["chain_seq"] == 1

    def test_each_entry_links_to_the_previous(self, ledger):
        first = ledger.append("acme", _span(1))
        second = ledger.append("acme", _span(2))
        assert second["prev_hash"] == first["entry_hash"]
        assert second["chain_seq"] == 2

    def test_entry_hash_is_reproducible(self, ledger):
        entry = ledger.append("acme", _span(1))
        assert entry["entry_hash"] == compute_entry_hash(
            "acme", 1, entry["prev_hash"], entry["payload_hash"]
        )

    def test_identical_payloads_get_distinct_hashes(self, ledger):
        # Position is part of the hash, so a replayed record is not
        # indistinguishable from the original.
        a = ledger.append("acme", _span(1))
        b = ledger.append("acme", _span(1))
        assert a["entry_hash"] != b["entry_hash"]

    def test_chains_are_independent_per_workspace(self, ledger):
        ledger.append("acme", _span(1, "acme"))
        other = ledger.append("globex", _span(1, "globex"))
        # A busy tenant must not renumber a quiet one's chain.
        assert other["chain_seq"] == 1
        assert other["prev_hash"] == GENESIS_HASH

    def test_head_tracks_the_last_entry(self, ledger):
        ledger.append("acme", _span(1))
        last = ledger.append("acme", _span(2))
        head = ledger.head("acme")
        assert head["head_hash"] == last["entry_hash"]
        assert head["chain_seq"] == 2

    def test_head_of_unknown_workspace_is_genesis(self, ledger):
        assert ledger.head("nobody")["head_hash"] == GENESIS_HASH

    def test_concurrent_appends_produce_a_gapless_chain(self, ledger):
        # A duplicated chain_seq or a forked prev_hash here would make the
        # chain unverifiable under ordinary load.
        def write(i):
            ledger.append("acme", _span(i))

        threads = [threading.Thread(target=write, args=(i,)) for i in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = ledger.verify("acme")
        assert result["valid"] is True
        assert result["entries_checked"] == 25


class TestVerify:
    def test_intact_chain_verifies(self, ledger):
        for i in range(5):
            ledger.append("acme", _span(i))
        result = ledger.verify("acme")
        assert result["valid"] is True
        assert result["entries_checked"] == 5

    def test_empty_chain_is_valid(self, ledger):
        assert ledger.verify("nobody")["valid"] is True

    def test_edited_payload_is_detected(self, ledger):
        for i in range(5):
            ledger.append("acme", _span(i))
        # The exact attack the ledger exists for: quietly change which provider
        # a request was sent to, after the fact.
        with ledger.engine.begin() as conn:
            row = conn.execute(
                text("SELECT payload FROM audit_entries WHERE chain_seq = 3")
            ).mappings().first()
            payload = json.loads(row["payload"])
            payload["attributes"]["provider"] = "openai"
            conn.execute(
                text("UPDATE audit_entries SET payload = :p WHERE chain_seq = 3"),
                {"p": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
            )

        result = ledger.verify("acme")
        assert result["valid"] is False
        assert result["broken_at"]["chain_seq"] == 3
        assert "payload" in result["detail"]

    def test_recomputed_hash_does_not_launder_an_edit(self, ledger):
        """Updating payload *and* payload_hash still breaks the link."""
        for i in range(5):
            ledger.append("acme", _span(i))
        with ledger.engine.begin() as conn:
            payload = {"tampered": True}
            body = canonical(payload)
            conn.execute(
                text(
                    "UPDATE audit_entries SET payload = :p, payload_hash = :h "
                    "WHERE chain_seq = 3"
                ),
                {"p": body, "h": hash_payload(payload)},
            )
        result = ledger.verify("acme")
        assert result["valid"] is False
        assert result["broken_at"]["chain_seq"] == 3

    def test_deleted_middle_entry_is_detected(self, ledger):
        for i in range(5):
            ledger.append("acme", _span(i))
        with ledger.engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_entries WHERE chain_seq = 3"))
        result = ledger.verify("acme")
        assert result["valid"] is False
        assert "missing" in result["detail"]

    def test_truncated_tail_is_detected(self, ledger):
        # Deleting the most recent entries leaves a self-consistent chain, so
        # only the stored head reveals it.
        for i in range(5):
            ledger.append("acme", _span(i))
        with ledger.engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_entries WHERE chain_seq >= 4"))
        result = ledger.verify("acme")
        assert result["valid"] is False
        assert "head" in result["detail"]

    def test_forged_link_is_detected(self, ledger):
        for i in range(5):
            ledger.append("acme", _span(i))
        with ledger.engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_entries SET prev_hash = :h WHERE chain_seq = 3"),
                {"h": "f" * 64},
            )
        result = ledger.verify("acme")
        assert result["valid"] is False
        assert result["broken_at"]["chain_seq"] == 3

    def test_verification_is_scoped_to_one_workspace(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i, "acme"))
            ledger.append("globex", _span(i, "globex"))
        with ledger.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE audit_entries SET payload = '{}' "
                    "WHERE workspace_id = 'globex' AND chain_seq = 2"
                )
            )
        # One tenant's corruption must not invalidate another's evidence.
        assert ledger.verify("acme")["valid"] is True
        assert ledger.verify("globex")["valid"] is False


class TestRetention:
    def test_default_is_ninety_days(self, ledger):
        policy = ledger.get_retention("acme")
        assert policy["retention_days"] == 90
        assert policy["legal_hold"] is False

    def test_retention_is_per_workspace(self, ledger):
        ledger.set_retention("acme", retention_days=7)
        assert ledger.get_retention("acme")["retention_days"] == 7
        assert ledger.get_retention("globex")["retention_days"] == 90

    def test_legal_hold_can_be_set_independently(self, ledger):
        ledger.set_retention("acme", retention_days=7)
        ledger.set_retention("acme", legal_hold=True)
        policy = ledger.get_retention("acme")
        assert policy["legal_hold"] is True
        assert policy["retention_days"] == 7

    def test_legal_hold_can_be_lifted(self, ledger):
        ledger.set_retention("acme", legal_hold=True)
        ledger.set_retention("acme", legal_hold=False)
        assert ledger.get_retention("acme")["legal_hold"] is False


def _age_entries(ledger, workspace, days):
    old = datetime.utcnow() - timedelta(days=days)
    with ledger.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE audit_entries SET recorded_at = :t WHERE workspace_id = :w"
            ),
            {"t": old, "w": workspace},
        )


class TestPrune:
    def test_recent_entries_survive(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        result = ledger.prune("acme")
        assert result["pruned"]["acme"]["deleted"] == 0

    def test_expired_entries_are_removed(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        _age_entries(ledger, "acme", 120)
        assert ledger.prune("acme")["pruned"]["acme"]["deleted"] == 3

    def test_legal_hold_suspends_deletion(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        _age_entries(ledger, "acme", 400)
        ledger.set_retention("acme", legal_hold=True)
        result = ledger.prune("acme")
        assert result["pruned"]["acme"]["skipped"] == "legal_hold"
        assert result["pruned"]["acme"]["deleted"] == 0

    def test_shorter_window_prunes_sooner(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        _age_entries(ledger, "acme", 10)
        assert ledger.prune("acme")["pruned"]["acme"]["deleted"] == 0
        ledger.set_retention("acme", retention_days=5)
        assert ledger.prune("acme")["pruned"]["acme"]["deleted"] == 3

    def test_pruned_chain_still_verifies(self, ledger):
        """Truncation must not be mistaken for tampering."""
        for i in range(3):
            ledger.append("acme", _span(i))
        _age_entries(ledger, "acme", 120)
        for i in range(3, 6):
            ledger.append("acme", _span(i))

        ledger.prune("acme")
        result = ledger.verify("acme")
        assert result["valid"] is True
        assert result["entries_checked"] == 3
        assert result["first_seq"] == 4

    def test_tampering_after_pruning_is_still_detected(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        _age_entries(ledger, "acme", 120)
        for i in range(3, 6):
            ledger.append("acme", _span(i))
        ledger.prune("acme")

        with ledger.engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_entries SET payload = '{}' WHERE chain_seq = 5")
            )
        assert ledger.verify("acme")["valid"] is False

    def test_prune_across_all_workspaces_respects_each_policy(self, ledger):
        for ws in ("acme", "globex"):
            for i in range(2):
                ledger.append(ws, _span(i, ws))
            _age_entries(ledger, ws, 200)
        ledger.set_retention("globex", legal_hold=True)

        result = ledger.prune()
        assert result["pruned"]["acme"]["deleted"] == 2
        assert result["pruned"]["globex"]["skipped"] == "legal_hold"


class TestReads:
    def test_entries_are_newest_first(self, ledger):
        for i in range(3):
            ledger.append("acme", _span(i))
        rows = ledger.entries("acme")
        assert [r["chain_seq"] for r in rows] == [3, 2, 1]

    def test_payload_is_returned_parsed(self, ledger):
        ledger.append("acme", _span(1))
        assert ledger.entries("acme")[0]["payload"]["service"] == "router"

    def test_entries_filter_by_type(self, ledger):
        ledger.append("acme", _span(1), entry_type="span")
        ledger.append("acme", _span(2), entry_type="decision")
        assert len(ledger.entries("acme", entry_type="decision")) == 1

    def test_entries_are_scoped_to_the_workspace(self, ledger):
        ledger.append("acme", _span(1, "acme"))
        ledger.append("globex", _span(1, "globex"))
        assert len(ledger.entries("acme")) == 1

    def test_stats_report_the_backend(self, ledger):
        ledger.append("acme", _span(1))
        stats = ledger.stats()
        assert stats["total_entries"] == 1
        assert stats["workspaces"] == 1
        assert stats["backend"] == "sqlite"

    def test_stats_count_legal_holds(self, ledger):
        ledger.append("acme", _span(1))
        ledger.set_retention("acme", legal_hold=True)
        assert ledger.stats()["legal_holds"] == 1
