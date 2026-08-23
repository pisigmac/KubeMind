"""Workspace-bound authentication, shared by every service."""

import pytest

from kubemind_auth import (
    AuthError,
    Authenticator,
    cors_origins,
    valid_workspace,
)


class TestProductionDeployment:
    def test_production_forces_required_and_refuses_open_mode(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "production")
        monkeypatch.delenv("KUBEMIND_API_KEYS", raising=False)
        a = Authenticator.from_config({})
        assert a.required is True
        with pytest.raises(RuntimeError, match="open-mode"):
            a.assert_production_safe("router")
        with pytest.raises(AuthError) as e:
            a.authenticate(None, "team-a")
        assert e.value.status_code == 503

    def test_production_with_keys_is_safe(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "production")
        monkeypatch.setenv("KUBEMIND_API_KEYS", "k1:acme")
        a = Authenticator.from_config({})
        a.assert_production_safe("router")
        assert a.authenticate("k1", None).workspace_id == "acme"

    def test_unknown_deployment_fails_closed(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "staging")
        with pytest.raises(ValueError, match="local or production"):
            Authenticator.from_config({})


class TestOpenMode:
    def test_no_keys_trusts_header(self):
        a = Authenticator()
        result = a.authenticate(None, "team-a")
        assert result.workspace_id == "team-a"
        assert result.authenticated is False
        assert a.open_mode is True

    def test_no_header_falls_back_to_default(self):
        assert Authenticator().authenticate(None, None).workspace_id == "default"

    def test_malformed_workspace_rejected(self):
        with pytest.raises(AuthError) as e:
            Authenticator().authenticate(None, "../etc/passwd")
        assert e.value.status_code == 400

    def test_required_refuses_when_unconfigured(self):
        a = Authenticator(required=True)
        with pytest.raises(AuthError) as e:
            a.authenticate(None, "team-a")
        assert e.value.status_code == 503


class TestKeyBinding:
    def test_valid_key_yields_its_workspace(self):
        a = Authenticator({"k1": "acme"})
        result = a.authenticate("k1", None)
        assert result.workspace_id == "acme"
        assert result.authenticated is True

    def test_missing_key_rejected(self):
        with pytest.raises(AuthError) as e:
            Authenticator({"k1": "acme"}).authenticate(None, None)
        assert e.value.status_code == 401

    def test_wrong_key_rejected(self):
        with pytest.raises(AuthError):
            Authenticator({"k1": "acme"}).authenticate("nope", None)

    def test_header_cannot_redirect_to_another_workspace(self):
        """The whole point: the header must not override the key."""
        with pytest.raises(AuthError) as e:
            Authenticator({"k1": "acme"}).authenticate("k1", "victim")
        assert e.value.status_code == 403

    def test_matching_header_is_allowed(self):
        result = Authenticator({"k1": "acme"}).authenticate("k1", "acme")
        assert result.workspace_id == "acme"

    def test_multiple_keys_map_independently(self):
        a = Authenticator({"k1": "acme", "k2": "globex"})
        assert a.authenticate("k1", None).workspace_id == "acme"
        assert a.authenticate("k2", None).workspace_id == "globex"


class TestServiceKey:
    def test_service_key_may_act_for_any_workspace(self):
        # The router proxies mind and sentinel for every tenant, so it cannot
        # use a key bound to one workspace.
        a = Authenticator({"k1": "acme"}, service_key="svc")
        result = a.authenticate("svc", "globex")
        assert result.workspace_id == "globex"
        assert result.is_service is True
        assert result.authenticated is True

    def test_service_key_scoping_is_unrestricted(self):
        a = Authenticator(service_key="svc")
        auth = a.authenticate("svc", "one")
        assert a.resolve_requested_workspace(auth, "two") == "two"

    def test_service_key_still_validates_workspace_shape(self):
        a = Authenticator(service_key="svc")
        with pytest.raises(AuthError):
            a.authenticate("svc", "../etc")

    def test_normal_key_is_not_a_service_key(self):
        a = Authenticator({"k1": "acme"}, service_key="svc")
        assert a.authenticate("k1", None).is_service is False


class TestRequestedWorkspaceScoping:
    def test_authenticated_caller_cannot_name_another_workspace(self):
        """Closes sentinel's `?workspace_id=` cross-tenant read."""
        a = Authenticator({"k1": "acme"})
        auth = a.authenticate("k1", None)
        with pytest.raises(AuthError) as e:
            a.resolve_requested_workspace(auth, "victim")
        assert e.value.status_code == 403

    def test_own_workspace_allowed(self):
        a = Authenticator({"k1": "acme"})
        auth = a.authenticate("k1", None)
        assert a.resolve_requested_workspace(auth, "acme") == "acme"

    def test_absent_request_defaults_to_own(self):
        a = Authenticator({"k1": "acme"})
        auth = a.authenticate("k1", None)
        assert a.resolve_requested_workspace(auth, None) == "acme"

    def test_open_mode_still_validates_shape(self):
        a = Authenticator()
        auth = a.authenticate(None, "team-a")
        with pytest.raises(AuthError):
            a.resolve_requested_workspace(auth, "bad/name")


class TestConfigLoading:
    def test_env_keys(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_API_KEYS", "k1:acme, k2:globex")
        a = Authenticator.from_config()
        assert a.keys == {"k1": "acme", "k2": "globex"}

    def test_malformed_env_entries_ignored(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_API_KEYS", "garbage,,k1:acme")
        assert Authenticator.from_config().keys == {"k1": "acme"}

    def test_config_keys_resolve_env_placeholders(self, monkeypatch):
        monkeypatch.delenv("KUBEMIND_API_KEYS", raising=False)
        monkeypatch.setenv("ACME_KEY", "secret123")
        a = Authenticator.from_config({"auth": {"keys": {"${ACME_KEY}": "acme"}}})
        assert a.keys == {"secret123": "acme"}

    def test_env_overrides_config(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_API_KEYS", "k1:from_env")
        a = Authenticator.from_config({"auth": {"keys": {"k1": "from_config"}}})
        assert a.keys["k1"] == "from_env"

    def test_required_from_env(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_AUTH_REQUIRED", "true")
        assert Authenticator.from_config().required is True


class TestCors:
    def test_default_is_not_wildcard(self, monkeypatch):
        monkeypatch.delenv("KUBEMIND_CORS_ORIGINS", raising=False)
        assert "*" not in cors_origins()

    def test_explicit_list(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_CORS_ORIGINS", "https://a.com, https://b.com")
        assert cors_origins() == ["https://a.com", "https://b.com"]

    def test_wildcard_is_rejected(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_CORS_ORIGINS", "*")
        with pytest.raises(ValueError, match="wildcard"):
            cors_origins()


def test_valid_workspace():
    assert valid_workspace("team-a_1")
    assert not valid_workspace("")
    assert not valid_workspace("a/b")
