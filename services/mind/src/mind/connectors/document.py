import os
import uuid
from typing import List, Dict

class DocumentConnector:
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.text_extensions = {".txt", ".md", ".py", ".js", ".ts", ".go", ".rs", ".json", ".yaml", ".yml", ".html", ".css", ".sh", ".sql"}

    async def ingest(self, path: str, node_type: str, workspace_id: str) -> List[Dict]:
        nodes = []

        if os.path.isdir(path):
            nodes = await self._ingest_directory(path, node_type, workspace_id)
        elif os.path.isfile(path):
            nodes = [await self._ingest_file(path, node_type, workspace_id)]

        return [n for n in nodes if n is not None]

    async def _ingest_directory(self, path: str, node_type: str, workspace_id: str) -> List[Dict]:
        nodes = []
        for root, _, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    node = await self._ingest_file(fpath, node_type, workspace_id)
                    if node:
                        nodes.append(node)
                except Exception as e:
                    print(f"[mind] Skipping {fpath}: {e}")
        return nodes

    async def _ingest_file(self, fpath: str, node_type: str, workspace_id: str) -> Dict:
        size = os.path.getsize(fpath)
        if size > self.max_file_size:
            return None

        ext = os.path.splitext(fpath)[1].lower()
        fname = os.path.basename(fpath)

        # Determine node type
        actual_type = node_type or "document"
        if ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".h"):
            actual_type = "code"

        # Read content
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return None

        # Detect language
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
            ".rs": "rust", ".java": "java", ".cpp": "cpp", ".c": "c",
        }
        language = lang_map.get(ext, "text")

        return {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "type": actual_type,
            "content": content[:50000],
            "metadata": {
                "path": fpath,
                "filename": fname,
                "extension": ext,
                "language": language,
                "size_bytes": size,
            },
        }
