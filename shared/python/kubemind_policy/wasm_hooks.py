"""Dynamic Extensibility & Wasm Plugin Hook Runner for KubeMind Policy Engine.

Enables custom pre-dispatch and post-dispatch filters, custom tokenizers,
and regulatory checks to execute inline with microsecond overhead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class HookContext:
    workspace_id: str
    model: str
    intent: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    allowed: bool
    modified_text: Optional[str] = None
    action: str = "allow"  # allow, redact, block, local_only
    reason: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


class WasmHookRunner:
    """Orchestrator for inline WebAssembly and Python extensibility hooks."""

    def __init__(self, fail_closed: bool = True):
        self.fail_closed = fail_closed
        self._pre_hooks: List[Callable[[str, HookContext], HookResult]] = []
        self._post_hooks: List[Callable[[str, HookContext], HookResult]] = []

    def register_pre_hook(self, hook_fn: Callable[[str, HookContext], HookResult]) -> None:
        """Register a hook executed before intent routing and dispatch."""
        self._pre_hooks.append(hook_fn)

    def register_post_hook(self, hook_fn: Callable[[str, HookContext], HookResult]) -> None:
        """Register a hook executed after model response generation."""
        self._post_hooks.append(hook_fn)

    def execute_pre_hooks(self, text: str, context: HookContext) -> HookResult:
        """Runs all registered pre-dispatch hooks sequentially."""
        current_text = text
        for hook in self._pre_hooks:
            try:
                res = hook(current_text, context)
                if not res.allowed or res.action == "block":
                    return res
                if res.modified_text is not None:
                    current_text = res.modified_text
            except Exception as e:
                if self.fail_closed:
                    return HookResult(
                        allowed=False,
                        action="block",
                        reason=f"Hook failure (fail-closed): {str(e)}",
                    )
        return HookResult(allowed=True, modified_text=current_text, action="allow")

    def execute_post_hooks(self, text: str, context: HookContext) -> HookResult:
        """Runs all registered post-dispatch hooks sequentially."""
        current_text = text
        for hook in self._post_hooks:
            try:
                res = hook(current_text, context)
                if not res.allowed or res.action == "block":
                    return res
                if res.modified_text is not None:
                    current_text = res.modified_text
            except Exception as e:
                if self.fail_closed:
                    return HookResult(
                        allowed=False,
                        action="block",
                        reason=f"Post-hook failure: {str(e)}",
                    )
        return HookResult(allowed=True, modified_text=current_text, action="allow")


_GLOBAL_HOOK_RUNNER = WasmHookRunner()


def get_default_hook_runner() -> WasmHookRunner:
    return _GLOBAL_HOOK_RUNNER
