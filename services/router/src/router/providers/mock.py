"""Mock local provider for zero-download fast local development and testing."""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict

from router.providers.base import BaseProvider


class MockLocalProvider(BaseProvider):
    def __init__(self, name: str = "mock-local", config: Dict[str, Any] | None = None):
        cfg = config or {}
        cfg.setdefault("local", True)
        cfg.setdefault("free", True)
        cfg.setdefault("models", ["llama3.1", "deepseek-r1", "gpt-4o-mini", "mock-model", "default"])
        super().__init__(name, cfg)

    async def chat(self, request: Any) -> Dict[str, Any]:
        if not self.can_execute():
            raise Exception(f"Circuit breaker OPEN for {self.name}")

        user_content = ""
        for m in getattr(request, "messages", []):
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
            if role == "user":
                user_content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")

        # Deterministic synthetic response echoing user intent
        response_text = (
            f"[KubeMind Local Dev Mock] Processed request for model '{getattr(request, 'model', 'mock-model')}'. "
            f"Input received: '{user_content[:60]}...' (Local offline dev response)"
            if user_content
            else "[KubeMind Local Dev Mock] Ready."
        )

        prompt_tokens = max(1, len(user_content.split()))
        completion_tokens = max(1, len(response_text.split()))

        self.record_success()

        return {
            "id": f"chatcmpl-mock-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": getattr(request, "model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    async def chat_stream(self, request: Any) -> AsyncIterator[str]:
        """Stream chunks via Server-Sent Events."""
        resp = await self.chat(request)
        content = resp["choices"][0]["message"]["content"]
        words = content.split(" ")
        req_id = resp["id"]
        model = resp["model"]
        created = resp["created"]

        for i, word in enumerate(words):
            chunk_text = word if i == len(words) - 1 else word + " "
            chunk_data = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
            await asyncio.sleep(0.005)

        # Final stop chunk
        stop_data = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(stop_data)}\n\n"
        yield "data: [DONE]\n\n"

    async def check_health(self) -> bool:
        self.healthy = True
        self.last_health_check = time.time()
        return True
