import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

class TraceStore:
    def __init__(self):
        self.db_path = os.environ.get("BEACON_DB_PATH", "./data/beacon-trace.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = None

    async def init(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                span_id TEXT,
                parent_id TEXT,
                workspace_id TEXT,
                service TEXT,
                operation TEXT,
                start_time TEXT,
                end_time TEXT,
                status TEXT,
                attributes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace ON spans(workspace_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_service ON spans(service)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON spans(created_at)")
        self.conn.commit()

    async def save_span(self, span: Dict[str, Any]):
        self.conn.execute("""
            INSERT INTO spans (trace_id, span_id, parent_id, workspace_id, service, operation, start_time, end_time, status, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            span["trace_id"], span["span_id"], span.get("parent_id"),
            span.get("workspace_id", "default"), span["service"], span["operation"],
            span["start_time"].isoformat() if isinstance(span["start_time"], datetime) else span["start_time"],
            span.get("end_time", "").isoformat() if isinstance(span.get("end_time"), datetime) else span.get("end_time", ""),
            span["status"], json.dumps(span.get("attributes", {}))
        ))
        self.conn.commit()

    async def query(self, workspace_id: str, service: Optional[str], limit: int) -> List[Dict]:
        sql = "SELECT * FROM spans WHERE workspace_id = ?"
        params = [workspace_id]
        if service:
            sql += " AND service = ?"
            params.append(service)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(sql, params)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    async def aggregate(self, workspace_id: str) -> Dict:
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_spans,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                service,
                operation
            FROM spans
            WHERE workspace_id = ?
            GROUP BY service, operation
        """, (workspace_id,))

        breakdown = {}
        total = 0
        errors = 0
        for row in cursor.fetchall():
            service, operation = row[2], row[3]
            count = row[0]
            err = row[1]
            total += count
            errors += err
            breakdown[f"{service}:{operation}"] = {"count": count, "errors": err}

        return {
            "workspace_id": workspace_id,
            "total_spans": total,
            "errors": errors,
            "error_rate": errors / total if total > 0 else 0,
            "breakdown": breakdown,
        }

    async def export(self, workspace_id: str) -> Dict:
        cursor = self.conn.execute(
            "SELECT * FROM spans WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,)
        )
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {"workspace_id": workspace_id, "spans": rows, "count": len(rows)}
