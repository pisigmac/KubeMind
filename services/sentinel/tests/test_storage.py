import pytest
import os
import tempfile
from sentinel.storage import TraceStore

class TestTraceStore:
    @pytest.fixture
    def store(self, tmp_path):
        # The path has to reach the constructor: setting `db_path` afterwards
        # left a cached connection pointing at the shared default database,
        # so tests collided on span_id and locked each other out.
        store = TraceStore(str(tmp_path / "spans.db"))
        yield store
        store.close()

    def test_save_and_query(self, store):
        span = {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "workspace_id": "default",
            "service": "router",
            "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00",
            "status": "ok",
            "attributes": {"model": "llama3.1"},
        }
        span_id = store.save_span(span)
        assert span_id > 0

        results = store.query("default")
        assert len(results) == 1
        assert results[0]["service"] == "router"
        assert results[0]["operation"] == "llm_call"

    def test_query_with_filters(self, store):
        store.save_span({
            "trace_id": "t1", "span_id": "s1", "workspace_id": "ws1",
            "service": "router", "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00", "status": "ok", "attributes": {},
        })
        store.save_span({
            "trace_id": "t2", "span_id": "s2", "workspace_id": "ws1",
            "service": "mind", "operation": "ingest",
            "start_time": "2024-01-01T00:00:00", "status": "ok", "attributes": {},
        })

        results = store.query("ws1", service="router")
        assert len(results) == 1
        assert results[0]["service"] == "router"

    def test_aggregate(self, store):
        store.save_span({
            "trace_id": "t1", "span_id": "s1", "workspace_id": "ws1",
            "service": "router", "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00", "status": "ok",
            "attributes": {"duration_ms": 100},
        })
        store.save_span({
            "trace_id": "t2", "span_id": "s2", "workspace_id": "ws1",
            "service": "router", "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00", "status": "error",
            "attributes": {"duration_ms": 200},
        })

        metrics = store.aggregate("ws1", hours=24)
        assert metrics["total_spans"] == 2
        assert metrics["total_errors"] == 1
        assert metrics["error_rate"] == 0.5
        assert "router" in metrics["services"]

    def test_export(self, store):
        store.save_span({
            "trace_id": "t1", "span_id": "s1", "workspace_id": "ws1",
            "service": "router", "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00", "status": "ok", "attributes": {},
        })

        result = store.export("ws1")
        assert result["count"] == 1
        assert len(result["spans"]) == 1
        assert "exported_at" in result

    def test_prune_old(self, store):
        # This would need actual old data; just test the method exists
        deleted = store.prune_old(days=0)
        assert deleted >= 0

    def test_stats(self, store):
        store.save_span({
            "trace_id": "t1", "span_id": "s1", "workspace_id": "ws1",
            "service": "router", "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00", "status": "ok", "attributes": {},
        })

        stats = store.get_stats()
        assert stats["total_spans"] == 1
        assert stats["workspaces"] == 1
        assert stats["services"] == 1
