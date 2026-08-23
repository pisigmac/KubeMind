import os
import shlex
import subprocess
import sys
from typing import Dict, Any, List

import httpx

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Any] = {}

    async def load(self):
        self.tools = {
            "filesystem": FilesystemTool(),
            "shell": ShellTool(),
            "web_search": WebSearchTool(),
            "knowledge": KnowledgeTool(),
            "code_analyzer": CodeAnalyzerTool(),
            "read_file": ReadFileTool(),
            "write_file": WriteFileTool(),
        }

    def list_schema(self) -> List[Dict]:
        return [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters,
                "enabled": True,
            }
            for name, tool in self.tools.items()
        ]

    async def invoke(self, tool_name: str, arguments: Dict, workspace_id: str) -> Any:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}
        return await tool.run(arguments, workspace_id)

class BaseTool:
    description = ""
    parameters = {}

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        raise NotImplementedError

class FilesystemTool(BaseTool):
    description = "Read, write, and list files in the workspace filesystem"
    parameters = {
        "path": {"type": "string", "description": "File or directory path"},
        "action": {"type": "string", "enum": ["read", "write", "list", "exists"]},
        "content": {"type": "string", "description": "Content to write (for write action)"},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        base = f"/tmp/tricore/{workspace_id}"
        os.makedirs(base, exist_ok=True)

        rel_path = arguments.get("path", "").lstrip("/").replace("..", "")
        path = os.path.join(base, rel_path)

        # Ensure path is within base directory
        if not path.startswith(base):
            return {"error": "Path traversal detected"}

        action = arguments.get("action", "read")

        if action == "read":
            if not os.path.exists(path):
                return {"error": "File not found", "path": path}
            if os.path.isdir(path):
                return {"error": "Path is a directory", "path": path}
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return {"content": f.read(), "path": path, "size": os.path.getsize(path)}

        elif action == "write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(arguments.get("content", ""))
            return {"status": "written", "path": path, "size": len(arguments.get("content", ""))}

        elif action == "list":
            if not os.path.exists(path):
                return {"error": "Directory not found", "path": path}
            if not os.path.isdir(path):
                return {"error": "Path is not a directory", "path": path}
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                items.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None,
                })
            return {"items": items, "path": path}

        elif action == "exists":
            return {"exists": os.path.exists(path), "path": path}

        return {"error": f"Unknown action: {action}"}

class ReadFileTool(BaseTool):
    description = "Read the contents of a file"
    parameters = {
        "path": {"type": "string", "description": "Path to the file"},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        fs = FilesystemTool()
        return await fs.run({"path": arguments.get("path"), "action": "read"}, workspace_id)

class WriteFileTool(BaseTool):
    description = "Write content to a file"
    parameters = {
        "path": {"type": "string", "description": "Path to the file"},
        "content": {"type": "string", "description": "Content to write"},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        fs = FilesystemTool()
        return await fs.run({
            "path": arguments.get("path"),
            "action": "write",
            "content": arguments.get("content", ""),
        }, workspace_id)

class ShellTool(BaseTool):
    description = "Execute shell commands safely"
    parameters = {
        "command": {"type": "string", "description": "Shell command to execute"},
        "timeout": {"type": "integer", "default": 30},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        cmd = arguments.get("command", "")
        timeout = arguments.get("timeout", 30)

        # Block dangerous patterns
        blocked_patterns = [
            "rm -rf /", "> /dev/null", "| sh", "| bash", "curl |",
            "wget |", "eval(", "exec(", "__import__(", "os.system",
            "subprocess.call", "subprocess.run",
        ]
        for pattern in blocked_patterns:
            if pattern in cmd:
                return {"error": f"Blocked command pattern: {pattern}", "blocked": True}

        # Whitelist approach for commands
        allowed_commands = {"python", "node", "git", "curl", "cat", "ls", "grep", "find", "echo", "wc", "head", "tail", "sort", "uniq", "pwd", "mkdir", "touch", "cp", "mv", "diff", "tree"}
        try:
            cmd_parts = shlex.split(cmd)
        except ValueError as exc:
            return {"error": f"Invalid command syntax: {exc}", "blocked": True}
        if cmd_parts and cmd_parts[0] not in allowed_commands:
            return {"error": f"Command not in allowlist: {cmd_parts[0]}", "allowed": list(allowed_commands)}

        if not cmd_parts:
            return {"error": "Command must not be empty", "blocked": True}

        try:
            result = subprocess.run(
                cmd_parts,
                shell=False,
                capture_output=True,
                text=True,
                timeout=min(timeout, 60),
                cwd=f"/tmp/tricore/{workspace_id}",
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": cmd,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out", "command": cmd, "timeout": timeout}
        except Exception as e:
            return {"error": str(e), "command": cmd}

class WebSearchTool(BaseTool):
    description = "Search the web using DuckDuckGo"
    parameters = {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "default": 5},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)

        try:
            # Use DuckDuckGo HTML interface (no API key needed)
            import urllib.parse
            encoded = urllib.parse.quote(query)

            result = subprocess.run(
                ["curl", "-s", "-L", f"https://html.duckduckgo.com/html/?q={encoded}"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            # Simple parsing of results
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.stdout, "html.parser")
            results = []

            for result_div in soup.find_all("div", class_="result")[:max_results]:
                title_a = result_div.find("a", class_="result__a")
                snippet = result_div.find("a", class_="result__snippet")

                if title_a:
                    results.append({
                        "title": title_a.get_text(strip=True),
                        "url": title_a.get("href", ""),
                        "snippet": snippet.get_text(strip=True) if snippet else "",
                    })

            return {"results": results, "query": query, "count": len(results)}

        except Exception as e:
            return {"error": str(e), "query": query}

class KnowledgeTool(BaseTool):
    description = "Query the knowledge graph (mind)"
    parameters = {
        "query": {"type": "string", "description": "Search query"},
        "filters": {"type": "object", "description": "Optional filters like {'type': 'code'}"},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        cw_url = os.environ.get("MIND_URL", os.environ.get("CONTEXTWEAVE_URL", "http://mind:8081"))

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{cw_url}/v1/query",
                    headers={
                        "X-Workspace-ID": workspace_id,
                        "Authorization": "Bearer tricore-local-dev-key",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": arguments.get("query", ""),
                        "filters": arguments.get("filters"),
                        "top_k": arguments.get("top_k", 5),
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

class CodeAnalyzerTool(BaseTool):
    description = "Analyze Python code for issues using ruff"
    parameters = {
        "path": {"type": "string", "description": "Path to Python file"},
        "fix": {"type": "boolean", "default": False, "description": "Auto-fix issues"},
    }

    async def run(self, arguments: Dict, workspace_id: str) -> Any:
        path = arguments.get("path", "")
        fix = arguments.get("fix", False)

        base = f"/tmp/tricore/{workspace_id}"
        full_path = os.path.join(base, path.lstrip("/"))

        if not os.path.exists(full_path):
            return {"error": "File not found", "path": full_path}

        if not full_path.endswith(".py"):
            return {"error": "Only Python files supported", "path": full_path}

        try:
            cmd = [sys.executable, "-m", "ruff", "check"]
            if fix:
                cmd.append("--fix")
            cmd.append(full_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "issues": result.stdout or "No issues found",
                "stderr": result.stderr,
                "returncode": result.returncode,
                "fixed": fix,
                "path": full_path,
            }
        except Exception as e:
            return {"error": str(e), "path": full_path}
