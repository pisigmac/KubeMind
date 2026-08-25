import os
import httpx
import asyncio
from typing import List, Optional

class EmbeddingGenerator:
    def __init__(self):
        try:
            from kubemind_config import get_ollama_base_url
            self.base_url = get_ollama_base_url().rstrip("/")
        except ImportError:
            self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
        self.dimensions = 768
        self.client: Optional[httpx.AsyncClient] = None
        self.is_ready = False

    async def init(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        # Verify Ollama is running and model is available
        try:
            resp = await self.client.get("/api/tags", timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                if self.model in model_names or any(self.model in n for n in model_names):
                    self.is_ready = True
                    print(f"[mind] Embedding model '{self.model}' ready")
                else:
                    print(f"[mind] WARNING: Model '{self.model}' not found in Ollama. Run: ollama pull {self.model}")
            else:
                print(f"[mind] WARNING: Ollama not responding at {self.base_url}")
        except Exception as e:
            print(f"[mind] WARNING: Could not connect to Ollama: {e}")

    async def embed(self, text: str) -> List[float]:
        if not self.client:
            raise RuntimeError("Embedding generator not initialized")

        # Truncate very long text (Ollama has context limits)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]

        try:
            resp = await self.client.post("/api/embed", json={
                "model": self.model,
                "input": text,
            })
            if resp.status_code != 200:
                resp = await self.client.post("/api/embeddings", json={
                    "model": self.model,
                    "prompt": text,
                })
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding") or (data.get("embeddings", [[]])[0] if data.get("embeddings") else [])

            if len(embedding) != self.dimensions:
                # Pad or truncate to expected dimensions
                if len(embedding) < self.dimensions:
                    embedding = embedding + [0.0] * (self.dimensions - len(embedding))
                else:
                    embedding = embedding[:self.dimensions]

            return embedding
        except Exception as e:
            print(f"[mind] Embedding failed: {e}")
            # Return zero vector as fallback
            return [0.0] * self.dimensions

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            emb = await self.embed(text)
            results.append(emb)
            # Small delay to avoid overwhelming Ollama
            await asyncio.sleep(0.05)
        return results

    async def close(self):
        if self.client:
            await self.client.aclose()
