from router.models import RouteRequest, ChatRequest, Message


def test_route_request_defaults():
    r = RouteRequest(prompt="hello")
    assert r.enable_cache is True
    assert r.preferred_target is None


def test_chat_request_routing_hints():
    c = ChatRequest(
        model="llama3.1",
        messages=[Message(role="user", content="hi")],
        preferred_target="deepseek-r1-local",
        enable_cache=False,
    )
    assert c.preferred_target == "deepseek-r1-local"
    assert c.enable_cache is False
