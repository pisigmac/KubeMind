import os
import httpx
import time
from typing import Any, Dict

from router.providers.base import BaseProvider

class OllamaProvider(BaseProvider):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        raw_url = config.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        if raw_url.startswith("${") and raw_url.endswith("}"):
            var_name = raw_url[2:-1]
            raw_url = os.environ.get(var_name, "http://ollama:11434")
        self.base_url = raw_url.rstrip("/")
        timeout = config.get("timeout_seconds", 120)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def chat(self, request: Any) -> Dict:
        if not self.can_execute():
            raise Exception(f"Circuit breaker OPEN for {self.name}")

        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens
        if request.top_p is not None:
            payload["options"]["top_p"] = request.top_p

        try:
            resp = await self.client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

            self.record_success()

            return {
                "id": f"chatcmpl-ollama-{int(time.time() * 1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": data.get("message", {}).get("content", ""),
                    },
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
        except Exception:
            self.record_failure()
            raise

    async def embeddings(self, request: Any) -> Dict:
        if not self.can_execute():
            raise Exception(f"Circuit breaker OPEN for {self.name}")

        inputs = request.input if isinstance(request.input, list) else [request.input]

        try:
            embeddings = []
            for idx, text in enumerate(inputs):
                resp = await self.client.post("/api/embeddings", json={
                    "model": request.model,
                    "prompt": text,
                })
                resp.raise_for_status()
                data = resp.json()
                embeddings.append({
                    "object": "embedding",
                    "embedding": data.get("embedding", []),
                    "index": idx,
                })

            self.record_success()

            return {
                "object": "list",
                "data": embeddings,
                "model": request.model,
                "usage": {
                    "prompt_tokens": sum(len(inp.split()) for inp in inputs),
                    "total_tokens": sum(len(inp.split()) for inp in inputs),
                },
            }
        except Exception:
            self.record_failure()
            raise

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get("/api/tags", timeout=10)
            if resp.status_code == 200:
                self.record_success()
                return True
        except Exception:
            pass
        self.record_failure()
        return False

    async def close(self):
        await self.client.aclose()
