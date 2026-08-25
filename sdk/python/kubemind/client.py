import os
import httpx
from typing import List, Dict, Any, Optional

class KubeMindClient:
    """
    Official Python SDK client for KubeMind.
    Provides standard wrappers around KubeMind services (Router, Mind, Sentinel).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_id: Optional[str] = None,
        router_url: Optional[str] = None,
        mind_url: Optional[str] = None,
        sentinel_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.workspace_id = workspace_id or os.environ.get("KUBEMIND_WORKSPACE", "default")
        resolved_router = router_url or os.environ.get("ROUTER_URL", os.environ.get("KUBEMIND_ROUTER_URL", "http://localhost:9080"))
        resolved_mind = mind_url or os.environ.get("MIND_URL", os.environ.get("KUBEMIND_MIND_URL", "http://localhost:9081"))
        resolved_sentinel = sentinel_url or os.environ.get("SENTINEL_URL", os.environ.get("KUBEMIND_SENTINEL_URL", "http://localhost:9083"))
        
        self.router_url = resolved_router.rstrip("/")
        self.mind_url = resolved_mind.rstrip("/")
        self.sentinel_url = resolved_sentinel.rstrip("/")
        self.timeout = timeout
        
        self.headers = {
            "Content-Type": "application/json",
            "X-Workspace-ID": self.workspace_id
        }
        if api_key:
            self.headers["X-API-Key"] = api_key

    def chat_completion(self, model: str, messages: List[Dict[str, str]], enable_cache: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Sends a prompt to the KubeMind Router for classification, policy overlay, and LLM completions.
        """
        url = f"{self.router_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "enable_cache": enable_cache,
            **kwargs
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def chat_stream(self, model: str, messages: List[Dict[str, str]], **kwargs):
        """
        Stream chat completion tokens in real-time with de-anonymization applied.
        """
        import json
        url = f"{self.router_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, headers=self.headers, json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                        try:
                            yield json.loads(line[6:])
                        except Exception:
                            continue

    def route(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Sends a prompt to KubeMind Router's intent routing proxy directly.
        """
        url = f"{self.router_url}/v1/route"
        payload = {
            "prompt": prompt,
            **kwargs
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def classify(self, prompt: str) -> Dict[str, Any]:
        """
        Dry-run classify the prompt intent and sensitivity.
        """
        url = f"{self.router_url}/v1/classify"
        payload = {
            "prompt": prompt
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def ingest_memory(self, content: str, source: str = "sdk", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingest documents/knowledge into the KubeMind knowledge graph (Mind).
        """
        url = f"{self.mind_url}/v1/ingest"
        payload = {
            "content": content,
            "source": source,
            "metadata": metadata or {}
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def query_memory(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query the memory knowledge graph.
        """
        url = f"{self.mind_url}/v1/query"
        payload = {
            "query": query,
            "filters": filters or {}
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def verify_audit_ledger(self, limit: int = 50) -> Dict[str, Any]:
        """
        Verify and fetch the audit ledger entries from Sentinel.
        """
        url = f"{self.sentinel_url}/v1/audit/verify"
        params = {
            "workspace_id": self.workspace_id,
            "limit": limit
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def get_cost_analytics(self, window_hours: int = 24) -> Dict[str, Any]:
        """
        Fetch aggregated cost, token, and provider usage analytics.
        """
        url = f"{self.router_url}/v1/usage/analytics"
        params = {
            "window_hours": window_hours
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def get_org_analytics(self, window_hours: int = 720) -> Dict[str, Any]:
        """
        Fetch cross-workspace org-wide financial and token rollups.
        """
        url = f"{self.router_url}/v1/usage/org-analytics"
        params = {
            "window_hours": window_hours
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

