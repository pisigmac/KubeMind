import httpx
import uuid
from typing import List, Dict
from bs4 import BeautifulSoup

class WebConnector:
    def __init__(self):
        self.timeout = 30
        self.user_agent = "TricoreBot/0.1"

    async def ingest(self, url: str, node_type: str, workspace_id: str) -> List[Dict]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": self.user_agent})
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")

        if "text/html" in content_type:
            return await self._parse_html(resp.text, url, node_type, workspace_id)
        elif "text/plain" in content_type or "text/markdown" in content_type:
            return [{
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "type": node_type or "document",
                "content": resp.text[:50000],
                "metadata": {"title": url, "source_url": url, "content_type": content_type},
            }]
        else:
            # For other types, just store metadata
            return [{
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "type": node_type or "document",
                "content": f"Binary content from {url}",
                "metadata": {"title": url, "source_url": url, "content_type": content_type, "size": len(resp.content)},
            }]

    async def _parse_html(self, html: str, url: str, node_type: str, workspace_id: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "advertisement"]):
            tag.decompose()

        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else url

        # Extract main content
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup.body
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        return [{
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "type": node_type or "web_page",
            "content": text[:50000],
            "metadata": {
                "title": title,
                "source_url": url,
                "content_type": "text/html",
                "word_count": len(text.split()),
            },
        }]
