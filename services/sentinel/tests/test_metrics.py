from sentinel import metrics as prom_metrics


def test_render_prometheus_contains_counters():
    prom_metrics.record_span("router", "ok")
    prom_metrics.record_redaction(1)
    body = prom_metrics.render_prometheus(websocket_connections=2)
    assert "kubemind_spans_ingested_total" in body
    assert "kubemind_redactions_total" in body
    assert "kubemind_websocket_connections 2" in body
