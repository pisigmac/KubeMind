from kubemind_tracing import extract_correlation_id, generate_correlation_id


class TestCorrelationId:
    def test_generate_returns_prefixed_uuid(self):
        cid = generate_correlation_id()
        assert cid.startswith("km-")
        assert len(cid) == 39  # km- + 36 char uuid

    def test_extract_from_headers_uses_existing(self):
        cid = extract_correlation_id({"x-correlation-id": "km-abc123"})
        assert cid == "km-abc123"

    def test_extract_from_traceparent(self):
        cid = extract_correlation_id(
            {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        )
        assert cid == "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_extract_generates_new_when_missing(self):
        cid = extract_correlation_id({})
        assert cid.startswith("km-")
