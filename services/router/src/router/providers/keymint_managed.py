"""Credential-free provider metadata for KeyMint-backed runtime routing."""

from typing import Any, Dict

from router.providers.base import BaseProvider


class KeyMintManagedProvider(BaseProvider):
    """A selectable remote target that can never dispatch direct provider traffic.

    KubeMind uses this object only for model/policy ranking. The router
    exchanges a Connection reference for a short-lived KeyMint capability
    and sends the request through KeyMint's proxy.
    """

    async def chat(self, request: Any) -> Dict:
        raise RuntimeError("KEYMINT_CAPABILITY_REQUIRED")

    async def embeddings(self, request: Any) -> Dict:
        raise RuntimeError("KEYMINT_CAPABILITY_REQUIRED")

    async def health_check(self) -> bool:
        # This is catalog health, not provider reachability. KeyMint owns the
        # live provider check and proxy circuit state.
        return True

    def can_execute(self) -> bool:
        return False

    def can_route_via_keymint(self) -> bool:
        return self._breaker.can_execute()
