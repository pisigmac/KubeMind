"""End-to-End system verification suite for KubeMind."""

import pytest
from kubemind_auth import Authenticator, Role, AuthError
from kubemind_policy import detect, pseudonymize_string, restore_string
from kubemind_policy.ner import get_default_ner


class TestE2EPolicyAndPseudonymization:
    def test_ner_entity_pseudonymization_and_restoration(self):
        prompt = (
            "Patient: Dr. Sarah Connor lives at 1042 Elm Street and works at Cyberdyne Systems Inc. "
            "Please call 555-019-2834 or email sarah@cyberdyne.com."
        )

        # 1. Detection
        hits = detect(prompt)
        assert "person" in hits
        assert "address" in hits
        assert "organization" in hits
        assert "phone" in hits
        assert "email" in hits

        # 2. In-memory tokenization
        pseudonymized, token_map, modes_found = pseudonymize_string(prompt)
        assert "Sarah Connor" not in pseudonymized
        assert "1042 Elm Street" not in pseudonymized
        assert "Cyberdyne Systems Inc" not in pseudonymized
        assert "555-019-2834" not in pseudonymized
        assert "sarah@cyberdyne.com" not in pseudonymized

        # 3. Model response restoration
        llm_response = (
            f"Summary for {list(token_map.keys())[0]}: records forwarded to {list(token_map.keys())[1]}."
        )
        restored = restore_string(llm_response, token_map)
        assert token_map[list(token_map.keys())[0]] in restored
        assert token_map[list(token_map.keys())[1]] in restored


class TestE2ERBACPermissions:
    def test_auditor_role_rejection_for_chat(self, monkeypatch):
        monkeypatch.setenv(
            "KUBEMIND_API_KEYS",
            "key_admin:acme:admin, key_dev:acme:developer, key_auditor:acme:auditor, key_viewer:acme:viewer",
        )
        auth = Authenticator.from_config()

        # Auditor cannot chat
        auditor_ctx = auth.authenticate("key_auditor", None)
        assert auditor_ctx.role == Role.AUDITOR.value
        assert auditor_ctx.has_scope("audit:verify") is True
        assert auditor_ctx.has_scope("chat") is False
        with pytest.raises(AuthError) as exc:
            auditor_ctx.assert_scope("chat")
        assert exc.value.status_code == 403

        # Developer can chat but cannot verify audit
        dev_ctx = auth.authenticate("key_dev", None)
        assert dev_ctx.role == Role.DEVELOPER.value
        assert dev_ctx.has_scope("chat") is True
        assert dev_ctx.has_scope("audit:verify") is False

        # Admin can do everything
        admin_ctx = auth.authenticate("key_admin", None)
        assert admin_ctx.role == Role.ADMIN.value
        assert admin_ctx.has_scope("chat") is True
        assert admin_ctx.has_scope("audit:verify") is True
