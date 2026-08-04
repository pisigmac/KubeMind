"""In-process metrics for the router.

Deliberately dependency-free: sentinel renders Prometheus text the same way, so
adding a client library for four counters was not worth the image size.

State is per-process, which is fine for counters that Prometheus scrapes from
each replica independently. It is *not* a substitute for the audit ledger --
these numbers are for operators, the ledger is for auditors.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict

_lock = threading.Lock()

_requests_total = 0
_by_intent: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {
        "requests": 0,
        "cache_hits": 0,
        "billable": 0,
        "latency_ms_sum": 0.0,
        "errors": 0,
        "abstained": 0,
        "retrieval": 0,
        "local_only": 0,
    }
)
_by_provider: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {"requests": 0, "errors": 0, "latency_ms_sum": 0.0, "fallbacks": 0}
)
_policy_actions: Dict[str, int] = defaultdict(int)
_confidence_buckets: Dict[str, int] = defaultdict(int)

_BUCKETS = (0.2, 0.4, 0.6, 0.8, 0.9, 1.01)


def _bucket(value: float) -> str:
    for edge in _BUCKETS:
        if value < edge:
            return f"{edge}"
    return "+Inf"


def record_decision(record: Any) -> None:
    """Fold a DecisionRecord into the counters."""
    global _requests_total
    with _lock:
        _requests_total += 1

        intent = _by_intent[getattr(record, "intent", "general")]
        intent["requests"] += 1
        intent["latency_ms_sum"] += float(getattr(record, "latency_ms", 0.0) or 0.0)
        if getattr(record, "cache_hit", False):
            intent["cache_hits"] += 1
        if getattr(record, "billable", True):
            intent["billable"] += 1
        if getattr(record, "status", "ok") != "ok":
            intent["errors"] += 1
        if getattr(record, "intent_abstained", False):
            intent["abstained"] += 1
        if getattr(record, "retrieval_used", False):
            intent["retrieval"] += 1
        if getattr(record, "egress_class", "any") == "local_only":
            intent["local_only"] += 1

        provider_name = getattr(record, "provider", None)
        if provider_name:
            provider = _by_provider[provider_name]
            provider["requests"] += 1
            provider["latency_ms_sum"] += float(getattr(record, "latency_ms", 0.0) or 0.0)
            if getattr(record, "status", "ok") != "ok":
                provider["errors"] += 1
            if getattr(record, "fallback", False):
                provider["fallbacks"] += 1

        _policy_actions[getattr(record, "policy_action", "allow")] += 1
        _confidence_buckets[_bucket(float(getattr(record, "intent_confidence", 0.0) or 0.0))] += 1


def routing_report() -> Dict[str, Any]:
    with _lock:
        intents = {}
        for name, stats in _by_intent.items():
            requests = stats["requests"] or 1
            intents[name] = {
                "requests": stats["requests"],
                "cache_hits": stats["cache_hits"],
                "cache_hit_rate": round(stats["cache_hits"] / requests, 4),
                # Cache hits replay stored usage numbers; only billable
                # requests actually cost anything.
                "billable_requests": stats["billable"],
                "avg_latency_ms": round(stats["latency_ms_sum"] / requests, 3),
                "errors": stats["errors"],
                "abstained": stats["abstained"],
                "retrieval_used": stats["retrieval"],
                "local_only": stats["local_only"],
            }
        providers = {
            name: {
                "requests": stats["requests"],
                "errors": stats["errors"],
                "fallbacks": stats["fallbacks"],
                "avg_latency_ms": round(
                    stats["latency_ms_sum"] / (stats["requests"] or 1), 3
                ),
            }
            for name, stats in _by_provider.items()
        }
        return {
            "total_requests": _requests_total,
            "intents": intents,
            "providers": providers,
            "policy_actions": dict(_policy_actions),
            "intent_confidence_buckets": dict(_confidence_buckets),
        }


def render_prometheus() -> str:
    report = routing_report()
    lines = [
        "# HELP kubemind_router_requests_total Requests handled by the router",
        "# TYPE kubemind_router_requests_total counter",
        f"kubemind_router_requests_total {report['total_requests']}",
        "# HELP kubemind_router_intent_requests_total Requests by classified intent",
        "# TYPE kubemind_router_intent_requests_total counter",
    ]
    for intent, stats in report["intents"].items():
        lines.append(
            f'kubemind_router_intent_requests_total{{intent="{intent}"}} {stats["requests"]}'
        )
    lines += [
        "# HELP kubemind_router_cache_hits_total Cache hits by intent",
        "# TYPE kubemind_router_cache_hits_total counter",
    ]
    for intent, stats in report["intents"].items():
        lines.append(
            f'kubemind_router_cache_hits_total{{intent="{intent}"}} {stats["cache_hits"]}'
        )
    lines += [
        "# HELP kubemind_router_policy_actions_total Policy verdicts",
        "# TYPE kubemind_router_policy_actions_total counter",
    ]
    for action, count in report["policy_actions"].items():
        lines.append(
            f'kubemind_router_policy_actions_total{{action="{action}"}} {count}'
        )
    lines += [
        "# HELP kubemind_router_provider_requests_total Requests by provider",
        "# TYPE kubemind_router_provider_requests_total counter",
    ]
    for provider, stats in report["providers"].items():
        lines.append(
            f'kubemind_router_provider_requests_total{{provider="{provider}"}} {stats["requests"]}'
        )
        lines.append(
            f'kubemind_router_provider_errors_total{{provider="{provider}"}} {stats["errors"]}'
        )
    lines += [
        "# HELP kubemind_router_intent_confidence Confidence distribution",
        "# TYPE kubemind_router_intent_confidence histogram",
    ]
    for bucket, count in sorted(report["intent_confidence_buckets"].items()):
        lines.append(
            f'kubemind_router_intent_confidence_bucket{{le="{bucket}"}} {count}'
        )
    return "\n".join(lines) + "\n"


def reset() -> None:
    """Test helper."""
    global _requests_total
    with _lock:
        _requests_total = 0
        _by_intent.clear()
        _by_provider.clear()
        _policy_actions.clear()
        _confidence_buckets.clear()
