"""Unit tests for Cloud KMS & Secret Manager Adapters."""

import os
import pytest
from router.kms import KMSResolver, KMSError, BaseKMSAdapter


class MockAdapter(BaseKMSAdapter):
    def resolve_secret(self, secret_id: str):
        if secret_id == "valid-key":
            return "sk-secret-12345"
        return None


def test_env_resolution(monkeypatch):
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-live-123")
    resolver = KMSResolver()
    assert resolver.resolve("env://TEST_OPENAI_KEY") == "sk-live-123"
    assert resolver.resolve("env://NON_EXISTENT") is None


def test_mock_adapter_resolution():
    resolver = KMSResolver()
    resolver.adapters["vault"] = MockAdapter()
    assert resolver.resolve("vault://valid-key") == "sk-secret-12345"
    assert resolver.resolve("vault://invalid-key") is None


def test_unconfigured_provider():
    resolver = KMSResolver()
    resolver.adapters.clear()
    with pytest.raises(KMSError) as exc_info:
        resolver.resolve("aws://my-secret")
    assert "KMS_PROVIDER_NOT_CONFIGURED" in str(exc_info.value)
