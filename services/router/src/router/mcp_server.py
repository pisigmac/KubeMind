"""Model Context Protocol (MCP) Server for KubeMind.

Exposes KubeMind tools and capabilities over JSON-RPC 2.0 stdio transport to
Claude Desktop, Cursor, and external AI agents.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List
import httpx

try:
    from kubemind_config import get_router_url, get_mind_url, get_sentinel_url
    ROUTER_URL = get_router_url()
    MIND_URL = get_mind_url()
    SENTINEL_URL = get_sentinel_url()
except ImportError:
    ROUTER_URL = os.environ.get("ROUTER_URL", "http://localhost:9080")
    MIND_URL = os.environ.get("MIND_URL", "http://localhost:9081")
    SENTINEL_URL = os.environ.get("SENTINEL_URL", "http://localhost:9083")

API_KEY = os.environ.get("KUBEMIND_API_KEY", "")
WORKSPACE_ID = os.environ.get("KUBEMIND_WORKSPACE", "default")


def get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "X-Workspace-ID": WORKSPACE_ID}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


TOOLS_DEFINITION = [
    {
        "name": "kubemind_route",
        "description": "Route a prompt through KubeMind for intent classification, sensitivity policy, and model execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt to route"},
                "model": {"type": "string", "description": "Optional model override (e.g. llama3.1, gpt-4o)"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "kubemind_mind_query",
        "description": "Query KubeMind hybrid vector knowledge graph for grounded organizational context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for knowledge graph"},
                "top_k": {"type": "integer", "description": "Max documents to retrieve", "default": 4},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kubemind_mind_ingest",
        "description": "Ingest document text or repository knowledge into KubeMind graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Document content to index"},
                "source": {"type": "string", "description": "Source identifier (e.g. handbook, repo)"},
            },
            "required": ["content", "source"],
        },
    },
    {
        "name": "kubemind_verify_audit",
        "description": "Cryptographically verify the SHA-256 tamper-evident Sentinel audit ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of ledger entries to verify", "default": 50},
            },
        },
    },
]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Any:
    headers = get_headers()
    with httpx.Client(timeout=15.0) as client:
        if name == "kubemind_route":
            prompt = arguments.get("prompt", "")
            model = arguments.get("model", "llama3.1")
            url = f"{ROUTER_URL}/v1/route"
            resp = client.post(url, headers=headers, json={"prompt": prompt, "model": model})
            resp.raise_for_status()
            return resp.json()

        elif name == "kubemind_mind_query":
            query = arguments.get("query", "")
            top_k = arguments.get("top_k", 4)
            url = f"{MIND_URL}/v1/query"
            resp = client.post(url, headers=headers, json={"query": query, "top_k": top_k})
            resp.raise_for_status()
            return resp.json()

        elif name == "kubemind_mind_ingest":
            content = arguments.get("content", "")
            source = arguments.get("source", "mcp")
            url = f"{MIND_URL}/v1/ingest"
            resp = client.post(url, headers=headers, json={"content": content, "source": source})
            resp.raise_for_status()
            return resp.json()

        elif name == "kubemind_verify_audit":
            limit = arguments.get("limit", 50)
            url = f"{SENTINEL_URL}/v1/audit/verify?workspace_id={WORKSPACE_ID}&limit={limit}"
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

        else:
            raise ValueError(f"Unknown tool: {name}")


def main():
    """Main JSON-RPC stdio event loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except Exception:
            continue

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        response: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}

        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "kubemind-mcp-server", "version": "0.3.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            response["result"] = {"tools": TOOLS_DEFINITION}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result = handle_tool_call(tool_name, tool_args)
                response["result"] = {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                }
            except Exception as e:
                response["result"] = {
                    "content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}],
                    "isError": True,
                }
        else:
            response["error"] = {"code": -32601, "message": f"Method '{method}' not found"}

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
