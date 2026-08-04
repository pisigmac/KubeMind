import httpx
import time
from typing import Any, Dict

from router.providers.base import BaseProvider

class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.base_url = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = config.get("api_key", "")
        timeout = config.get("timeout_seconds", 60)

        headers = {"Authorization": f"Bearer {self.api_key}"}
        if "openrouter" in name.lower():
            headers["HTTP-Referer"] = "https://kubemind.ai"
            headers["X-Title"] = "KubeMind"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def chat(self, request: Any) -> Dict:
        if not self.can_execute():
            raise Exception(f"Circuit breaker OPEN for {self.name}")

        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.stream:
            payload["stream"] = True

        try:
            resp = await self.client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.record_success()
            return data
        except Exception as e:
            self.record_failure()
            raise

    async def embeddings(self, request: Any) -> Dict:
        if not self.can_execute():
            raise Exception(f"Circuit breaker OPEN for {self.name}")

        payload = {
            "model": request.model,
            "input": request.input,
        }
        if request.encoding_format:
            payload["encoding_format"] = request.encoding_format
        if request.dimensions:
            payload["dimensions"] = request.dimensions

        try:
            resp = await self.client.post("/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.record_success()
            return data
        except Exception as e:
            self.record_failure()
            raise

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get("/models", timeout=10)
            if resp.status_code == 200:
                self.record_success()
                return True
        except Exception:
            pass
        self.record_failure()
        return False

    async def close(self):
        await self.client.aclose()
