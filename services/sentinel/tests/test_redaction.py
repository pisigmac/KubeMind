from sentinel.redaction import redact_string, redact_attributes


def test_redact_email():
    text, modes = redact_string("contact me at alice@example.com please")
    assert "alice@example.com" not in text
    assert "[REDACTED_EMAIL]" in text
    assert "email" in modes


def test_redact_aws_key():
    text, modes = redact_string("key AKIAIOSFODNN7EXAMPLE here")
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "aws_key" in modes


def test_redact_bearer():
    text, modes = redact_string("Authorization: Bearer abcdefghijklmnop123456")
    assert "abcdefghijklmnop123456" not in text
    assert "bearer" in modes


def test_redact_attributes_nested():
    attrs, modes = redact_attributes(
        {"prompt": "email bob@corp.io", "meta": {"token": "Bearer xyzsecrettokenvalue1"}}
    )
    assert "bob@corp.io" not in str(attrs)
    assert modes
    assert "attributes_redacted_fields" in attrs
