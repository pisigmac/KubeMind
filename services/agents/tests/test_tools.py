import pytest
from agents.tools import ToolRegistry, FilesystemTool, ShellTool, WebSearchTool, CodeAnalyzerTool

class TestToolRegistry:
    @pytest.mark.asyncio
    async def test_load_and_list_schema(self):
        registry = ToolRegistry()
        await registry.load()
        schemas = registry.list_schema()
        assert isinstance(schemas, list)
        assert len(schemas) > 0
        names = {s["name"] for s in schemas}
        assert "filesystem" in names
        assert "shell" in names


class TestFilesystemTool:
    @pytest.mark.asyncio
    async def test_read_write_list(self):
        tool = FilesystemTool()
        ws = "test-ws"

        # Write
        result = await tool.run({"path": "test.txt", "action": "write", "content": "hello world"}, ws)
        assert result["status"] == "written"

        # Read
        result = await tool.run({"path": "test.txt", "action": "read"}, ws)
        assert result["content"] == "hello world"

        # List
        result = await tool.run({"path": ".", "action": "list"}, ws)
        assert "items" in result
        assert any(i["name"] == "test.txt" for i in result["items"])

        # Exists
        result = await tool.run({"path": "test.txt", "action": "exists"}, ws)
        assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        tool = FilesystemTool()
        result = await tool.run({"path": "../../../etc/passwd", "action": "read"}, "test")
        assert "error" in result
        assert "traversal" in result["error"].lower()

class TestShellTool:
    @pytest.mark.asyncio
    async def test_allowed_command(self):
        tool = ShellTool()
        result = await tool.run({"command": "echo hello", "timeout": 5}, "test")
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_blocked_command(self):
        tool = ShellTool()
        result = await tool.run({"command": "rm -rf /"}, "test")
        assert result["blocked"] is True

    @pytest.mark.asyncio
    async def test_not_in_allowlist(self):
        tool = ShellTool()
        result = await tool.run({"command": "nc -l 8080"}, "test")
        assert "allowlist" in result["error"]

    @pytest.mark.asyncio
    async def test_shell_metacharacters_are_not_interpreted(self):
        tool = ShellTool()
        result = await tool.run({"command": "echo safe; uname"}, "test")
        assert result["returncode"] == 0
        assert result["stdout"].strip() == "safe; uname"

class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_search(self):
        tool = WebSearchTool()
        result = await tool.run({"query": "python programming", "max_results": 3}, "test")
        assert "results" in result
        assert "query" in result

class TestCodeAnalyzerTool:
    @pytest.mark.asyncio
    async def test_analyze_python(self):
        # CodeAnalyzerTool resolves paths under /tmp/tricore/{workspace_id}.
        # Write the fixture through FilesystemTool, then analyze by relative path.
        fs = FilesystemTool()
        await fs.run({"path": "sample.py", "action": "write", "content": "import os\n\ndef foo():\n    x = 1\n"}, "test")

        tool = CodeAnalyzerTool()
        result = await tool.run({"path": "sample.py", "fix": False}, "test")
        assert "issues" in result
        assert "returncode" in result
