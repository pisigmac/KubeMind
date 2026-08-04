import pytest
import os
import tempfile
from mind.connectors.web import WebConnector
from mind.connectors.document import DocumentConnector
from mind.connectors.git import GitConnector

class TestWebConnector:
    @pytest.mark.asyncio
    async def test_parse_html(self):
        conn = WebConnector()
        html = """
        <html><head><title>Test Page</title></head>
        <body>
            <nav>Nav content</nav>
            <main><h1>Hello World</h1><p>This is the main content.</p></main>
            <footer>Footer</footer>
        </body></html>
        """
        result = await conn._parse_html(html, "http://example.com", "web_page", "default")
        assert len(result) == 1
        assert result[0]["metadata"]["title"] == "Test Page"
        assert "Hello World" in result[0]["content"]
        assert "Nav content" not in result[0]["content"]
        assert "Footer" not in result[0]["content"]

class TestDocumentConnector:
    @pytest.mark.asyncio
    async def test_ingest_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    return 'world'\n")
            path = f.name

        try:
            conn = DocumentConnector()
            result = await conn.ingest(path, "code", "default")
            assert len(result) == 1
            assert result[0]["type"] == "code"
            assert result[0]["metadata"]["language"] == "python"
            assert "def hello" in result[0]["content"]
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            with open(os.path.join(tmpdir, "test.py"), "w") as f:
                f.write("x = 1\n")
            with open(os.path.join(tmpdir, "readme.md"), "w") as f:
                f.write("# Hello\n")

            conn = DocumentConnector()
            result = await conn.ingest(tmpdir, "document", "default")
            assert len(result) == 2
            types = {r["type"] for r in result}
            assert "code" in types
            assert "document" in types

class TestGitConnector:
    @pytest.mark.asyncio
    async def test_ingest_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Init git repo
            os.system(f"cd {tmpdir} && git init && git config user.email 'test@test.com' && git config user.name 'Test'")
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("print('hello')\n")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'init'")

            conn = GitConnector()
            result = await conn.ingest(tmpdir, "code", "default")
            assert len(result) >= 1
            assert result[0]["type"] == "code"
            assert result[0]["metadata"]["language"] == "python"
