import os
import json
import sqlite3
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager

class TraceStore:
    def __init__(self):
        self.db_path = os.environ.get("TRACER_DB_PATH", "./data/sentinel.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL UNIQUE,
                parent_id TEXT,
                workspace_id TEXT NOT NULL,
                service TEXT NOT NULL,
                operation TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL DEFAULT 'ok',
                attributes TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_spans_workspace ON spans(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_spans_service ON spans(service);
            CREATE INDEX IF NOT EXISTS idx_spans_operation ON spans(operation);
            CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
            CREATE INDEX IF NOT EXISTS idx_spans_time ON spans(created_at);
            CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);

            CREATE TABLE IF NOT EXISTS metrics_rollup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL,
                service TEXT NOT NULL,
                operation TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                span_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                avg_duration_ms REAL DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_rollup ON metrics_rollup(workspace_id, service, operation, period_start);
        """)
        conn.commit()

    def save_span(self, span: Dict[str, Any]) -> int:
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT INTO spans (trace_id, span_id, parent_id, workspace_id, service, operation, start_time, end_time, status, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            span["trace_id"],
            span["span_id"],
            span.get("parent_id"),
            span.get("workspace_id", "default"),
            span["service"],
            span["operation"],
            span["start_time"],
            span.get("end_time"),
            span.get("status", "ok"),
            json.dumps(span.get("attributes", {})),
        ))
        conn.commit()
        return cursor.lastrowid

    def query(self, workspace_id: str, service: Optional[str] = None, 
              operation: Optional[str] = None, status: Optional[str] = None,
              start_time: Optional[str] = None, end_time: Optional[str] = None,
              limit: int = 100, offset: int = 0) -> List[Dict]:
        conn = self._get_conn()

        sql = "SELECT * FROM spans WHERE workspace_id = ?"
        params = [workspace_id]

        if service:
            sql += " AND service = ?"
            params.append(service)
        if operation:
            sql += " AND operation = ?"
            params.append(operation)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if start_time:
            sql += " AND created_at >= ?"
            params.append(start_time)
        if end_time:
            sql += " AND created_at <= ?"
            params.append(end_time)

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            if isinstance(d.get("attributes"), str):
                try:
                    d["attributes"] = json.loads(d["attributes"])
                except Exception:
                    pass
            results.append(d)
        return results

    def aggregate(self, workspace_id: str, hours: int = 24) -> Dict[str, Any]:
        conn = self._get_conn()
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        # Overall stats
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_spans,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                AVG(CASE WHEN json_extract(attributes, '$.duration_ms') IS NOT NULL 
                    THEN json_extract(attributes, '$.duration_ms') END) as avg_duration
            FROM spans
            WHERE workspace_id = ? AND created_at >= ?
        """, (workspace_id, since))

        row = cursor.fetchone()
        total = row["total_spans"] or 0
        errors = row["errors"] or 0
        avg_duration = row["avg_duration"] or 0

        # Service breakdown
        cursor = conn.execute("""
            SELECT service, COUNT(*) as count, 
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                   AVG(CASE WHEN json_extract(attributes, '$.duration_ms') IS NOT NULL 
                       THEN json_extract(attributes, '$.duration_ms') END) as avg_duration
            FROM spans
            WHERE workspace_id = ? AND created_at >= ?
            GROUP BY service
        """, (workspace_id, since))

        services = {}
        for r in cursor.fetchall():
            services[r["service"]] = {
                "spans": r["count"],
                "errors": r["errors"],
                "avg_duration_ms": round(r["avg_duration"] or 0, 2),
                "error_rate": round((r["errors"] or 0) / r["count"], 4) if r["count"] > 0 else 0,
            }

        # Operation breakdown
        cursor = conn.execute("""
            SELECT operation, COUNT(*) as count,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
            FROM spans
            WHERE workspace_id = ? AND created_at >= ?
            GROUP BY operation
        """, (workspace_id, since))

        operations = {}
        for r in cursor.fetchall():
            operations[r["operation"]] = {
                "spans": r["count"],
                "errors": r["errors"],
            }

        return {
            "workspace_id": workspace_id,
            "total_spans": total,
            "total_errors": errors,
            "error_rate": round(errors / total, 4) if total > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "services": services,
            "operations": operations,
            "time_range": {"since": since, "until": datetime.utcnow().isoformat()},
        }

    def export(self, workspace_id: str, hours: Optional[int] = None) -> Dict[str, Any]:
        conn = self._get_conn()

        sql = "SELECT * FROM spans WHERE workspace_id = ?"
        params = [workspace_id]

        if hours:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            sql += " AND created_at >= ?"
            params.append(since)

        sql += " ORDER BY created_at"

        cursor = conn.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]

        return {
            "workspace_id": workspace_id,
            "spans": rows,
            "count": len(rows),
            "exported_at": datetime.utcnow().isoformat(),
        }

    def prune_old(self, days: int = 90):
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = conn.execute("DELETE FROM spans WHERE created_at < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) as total FROM spans")
        total = cursor.fetchone()["total"]

        cursor = conn.execute("SELECT COUNT(DISTINCT workspace_id) as workspaces FROM spans")
        workspaces = cursor.fetchone()["workspaces"]

        cursor = conn.execute("SELECT COUNT(DISTINCT service) as services FROM spans")
        services = cursor.fetchone()["services"]

        cursor = conn.execute("SELECT MAX(created_at) as latest FROM spans")
        latest = cursor.fetchone()["latest"]

        return {
            "total_spans": total,
            "workspaces": workspaces,
            "services": services,
            "latest_span": latest,
            "db_path": self.db_path,
        }
