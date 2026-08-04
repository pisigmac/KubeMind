import os
from typing import Dict, Optional

from mind.connectors.web import WebConnector
from mind.connectors.document import DocumentConnector
from mind.connectors.git import GitConnector

class ConnectorRegistry:
    def __init__(self):
        self.connectors: Dict[str, object] = {}

    async def load(self):
        self.connectors["web"] = WebConnector()
        self.connectors["document"] = DocumentConnector()
        self.connectors["git"] = GitConnector()

    def get_for_source(self, source: str) -> Optional[object]:
        if source.startswith("http://") or source.startswith("https://"):
            return self.connectors.get("web")

        # Check if it's a git repo
        git_path = os.path.join(source, ".git")
        if os.path.isdir(git_path) or source.endswith(".git"):
            return self.connectors.get("git")

        # Check if it's a directory
        if os.path.isdir(source):
            return self.connectors.get("document")

        # Check if it's a file or valid extension
        if os.path.isfile(source) or os.path.splitext(source)[1].lower() in (
            ".pdf", ".docx", ".txt", ".md", ".py", ".js", ".ts", ".go", ".rs", ".json", ".yaml", ".yml", ""
        ):
            return self.connectors.get("document")

        return None
