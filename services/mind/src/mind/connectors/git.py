import os
import uuid
import subprocess
from typing import List, Dict

class GitConnector:
    def __init__(self):
        self.max_files = 200

    async def ingest(self, repo_path: str, node_type: str, workspace_id: str) -> List[Dict]:
        # Verify it's a git repo
        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir):
            raise ValueError(f"Not a git repository: {repo_path}")

        # Get tracked files
        result = subprocess.run(
            ["git", "-C", repo_path, "ls-files"],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            raise ValueError(f"Failed to list git files: {result.stderr}")

        files = result.stdout.strip().split("\n")
        nodes = []

        for fpath in files[:self.max_files]:
            if not fpath:
                continue
            full_path = os.path.join(repo_path, fpath)
            if not os.path.isfile(full_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            ext = os.path.splitext(fpath)[1].lower()
            lang_map = {
                ".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
                ".rs": "rust", ".java": "java", ".cpp": "cpp", ".c": "c",
                ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin",
            }

            nodes.append({
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "type": "code",
                "content": content[:50000],
                "metadata": {
                    "repo": repo_path,
                    "path": fpath,
                    "language": lang_map.get(ext, "text"),
                    "extension": ext,
                },
            })

        return nodes
