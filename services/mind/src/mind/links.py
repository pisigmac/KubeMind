import os
from typing import List, Dict

class LinkDetector:
    def __init__(self, store):
        self.store = store
        self.similarity_threshold = float(os.environ.get("LINK_SIMILARITY_THRESHOLD", "0.75"))
        self.max_links_per_node = int(os.environ.get("MAX_LINKS_PER_NODE", "10"))

    async def detect_links(self, new_node_ids: List[str], workspace_id: str):
        # Get new nodes
        new_nodes = []
        for nid in new_node_ids:
            node = await self.store.get(nid, workspace_id)
            if node:
                new_nodes.append(node)

        # Get existing nodes in workspace
        existing_nodes = await self.store.get_all_nodes(workspace_id, limit=500)

        for new_node in new_nodes:
            links_created = 0

            # Method 1: Semantic similarity (if embeddings available)
            if new_node.get("embedding"):
                for existing in existing_nodes:
                    if existing["id"] == new_node["id"]:
                        continue
                    if not existing.get("embedding"):
                        continue

                    similarity = self._cosine_similarity(new_node["embedding"], existing["embedding"])
                    if similarity > self.similarity_threshold:
                        await self.store.create_link(
                            new_node["id"], existing["id"], "semantic", workspace_id
                        )
                        links_created += 1
                        if links_created >= self.max_links_per_node:
                            break

            # Method 2: Shared entities (URLs, file paths, keywords)
            if links_created < self.max_links_per_node:
                for existing in existing_nodes:
                    if existing["id"] == new_node["id"]:
                        continue

                    shared = self._find_shared_entities(new_node, existing)
                    if shared:
                        await self.store.create_link(
                            new_node["id"], existing["id"], "entity", workspace_id
                        )
                        links_created += 1
                        if links_created >= self.max_links_per_node:
                            break

            # Method 3: Same repository (for code nodes)
            if new_node["type"] == "code" and links_created < self.max_links_per_node:
                new_repo = new_node.get("metadata", {}).get("repo", "")
                for existing in existing_nodes:
                    if existing["id"] == new_node["id"]:
                        continue
                    if existing.get("metadata", {}).get("repo") == new_repo and new_repo:
                        await self.store.create_link(
                            new_node["id"], existing["id"], "same_repo", workspace_id
                        )
                        links_created += 1
                        if links_created >= self.max_links_per_node:
                            break

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _find_shared_entities(self, node_a: Dict, node_b: Dict) -> List[str]:
        shared = []

        # Check URLs
        url_a = node_a.get("metadata", {}).get("source_url", "")
        url_b = node_b.get("metadata", {}).get("source_url", "")
        if url_a and url_a == url_b:
            shared.append(url_a)

        # Check file paths
        path_a = node_a.get("metadata", {}).get("path", "")
        path_b = node_b.get("metadata", {}).get("path", "")
        if path_a and path_b:
            # Same directory
            dir_a = os.path.dirname(path_a)
            dir_b = os.path.dirname(path_b)
            if dir_a and dir_a == dir_b:
                shared.append(f"dir:{dir_a}")

        # Check common keywords in content
        words_a = set(node_a.get("content", "").lower().split())
        words_b = set(node_b.get("content", "").lower().split())
        common = words_a & words_b
        # Filter to meaningful words (length > 4)
        meaningful = [w for w in common if len(w) > 4]
        if len(meaningful) > 5:  # At least 5 shared meaningful words
            shared.extend(meaningful[:3])

        return shared
