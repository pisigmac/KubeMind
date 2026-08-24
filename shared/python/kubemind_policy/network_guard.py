"""Zero-Leak Network Egress Guard and Host Allowlist Enforcer for KubeMind.

Enforces strict domain, IP, and CIDR egress allowlists before any LLM dispatch
or tool execution, preventing data exfiltration to unauthorized external endpoints.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

# Default trusted LLM host suffixes
_DEFAULT_APPROVED_HOST_SUFFIXES = {
    "openai.com",
    "anthropic.com",
    "googleapis.com",
    "azure.com",
    "bedrock.amazonaws.com",
    "localhost",
    "127.0.0.1",
    "internal",
    "cluster.local",
}


@dataclass
class NetworkGuardVerdict:
    allowed: bool
    host: str
    action: str  # allow, block
    reason: Optional[str] = None


class NetworkEgressGuard:
    """Network egress boundary controller enforcing strict outbound host allowlists."""

    def __init__(
        self,
        allowed_hosts: Optional[Set[str]] = None,
        allowed_cidrs: Optional[List[str]] = None,
        fail_closed: bool = True,
    ):
        self.allowed_hosts = set(allowed_hosts) if allowed_hosts else set(_DEFAULT_APPROVED_HOST_SUFFIXES)
        self.allowed_cidrs = [ipaddress.ip_network(c) for c in (allowed_cidrs or ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"])]
        self.fail_closed = fail_closed

    def register_allowed_host(self, host_or_suffix: str) -> None:
        """Add an approved host or domain suffix to the allowlist."""
        self.allowed_hosts.add(host_or_suffix.lower().strip())

    def verify_egress_target(self, target_url: str) -> NetworkGuardVerdict:
        """Verifies whether an outbound HTTP/TCP target URL is approved for egress."""
        if not target_url:
            return NetworkGuardVerdict(allowed=False, host="", action="block", reason="Empty URL target")

        try:
            parsed = urlparse(target_url)
            host = (parsed.hostname or "").lower().strip()

            if not host:
                return NetworkGuardVerdict(allowed=False, host="", action="block", reason="Unparseable host")

            # 1. Check direct host allowlist and wildcard domain suffix match
            for approved in self.allowed_hosts:
                if host == approved or host.endswith("." + approved):
                    return NetworkGuardVerdict(allowed=True, host=host, action="allow")

            # 2. Check IP address CIDR bounds
            try:
                ip_obj = ipaddress.ip_address(host)
                for net in self.allowed_cidrs:
                    if ip_obj in net:
                        return NetworkGuardVerdict(allowed=True, host=host, action="allow")
            except ValueError:
                pass  # Host is a DNS hostname, not an IP address

            # Target is unapproved
            return NetworkGuardVerdict(
                allowed=False,
                host=host,
                action="block",
                reason=f"Host '{host}' is not in the approved egress allowlist (Anti-Exfiltration Rule)",
            )
        except Exception as e:
            if self.fail_closed:
                return NetworkGuardVerdict(
                    allowed=False,
                    host="",
                    action="block",
                    reason=f"Network guard inspection failed (fail-closed): {str(e)}",
                )
            return NetworkGuardVerdict(allowed=True, host="unknown", action="allow")


_GLOBAL_NETWORK_GUARD = NetworkEgressGuard()


def get_default_network_guard() -> NetworkEgressGuard:
    return _GLOBAL_NETWORK_GUARD
