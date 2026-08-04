import os
from typing import List, Dict, Optional, Any

from mind.storage import KnowledgeStore
from mind.embeddings import EmbeddingGenerator

class HybridSearcher:
    def __init__(self, store: KnowledgeStore, embedder: EmbeddingGenerator):
        self.store = store
        self.embedder = embedder
        self.vector_weight = float(os.environ.get("VECTOR_WEIGHT", "0.5"))
        self.keyword_weight = float(os.environ.get("KEYWORD_WEIGHT", "0.3"))
        self.graph_weight = float(os.environ.get("GRAPH_WEIGHT", "0.2"))

    async def search(self, query: str, filters: Optional[Dict[str, str]], workspace_id: str, top_k: int = 10) -> List[Dict]:
        # 1. Vector search
        query_embedding = await self.embedder.embed(query)
        vector_results = await self.store.search_by_vector(
            query_embedding, workspace_id, filters, limit=top_k * 3
        )

        # 2. Keyword search
        keyword_results = await self.store.search_by_keyword(
            query, workspace_id, filters, limit=top_k * 3
        )

        # 3. Graph search (nodes linked to top vector results)
        graph_results = await self._graph_search(vector_results, workspace_id, top_k * 2)

        # 4. Merge and score
        merged = self._merge_results(vector_results, keyword_results, graph_results)

        # 5. Sort by combined score and return top_k
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:top_k]

    async def _graph_search(self, seed_results: List[Dict], workspace_id: str, limit: int) -> List[Dict]:
        if not seed_results:
            return []

        # Find nodes linked to top vector results
        linked_ids = set()
        for seed in seed_results[:5]:
            links = await self.store.get_links(seed["id"], workspace_id)
            for link in links:
                other_id = link["target_id"] if link["source_id"] == seed["id"] else link["source_id"]
                linked_ids.add(other_id)

        if not linked_ids:
            return []

        # Fetch linked nodes
        results = []
        for node_id in list(linked_ids)[:limit]:
            node = await self.store.get(node_id, workspace_id)
            if node:
                results.append({
                    "id": node["id"],
                    "type": node["type"],
                    "content": node["content"][:1000],
                    "metadata": node["metadata"],
                    "score": 0.5,  # Base graph score
                })
        return results

    def _merge_results(self, vector: List[Dict], keyword: List[Dict], graph: List[Dict]) -> List[Dict]:
        by_id = {}

        # Normalize vector scores to 0-1
        if vector:
            max_v = max(r["score"] for r in vector)
            min_v = min(r["score"] for r in vector)
            v_range = max_v - min_v if max_v > min_v else 1
            for r in vector:
                nid = r["id"]
                norm_score = (r["score"] - min_v) / v_range if v_range > 0 else 1
                by_id[nid] = {
                    "id": nid,
                    "type": r["type"],
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "vector_score": norm_score,
                    "keyword_score": 0,
                    "graph_score": 0,
                }

        # Normalize keyword scores
        if keyword:
            max_k = max(r["score"] for r in keyword)
            min_k = min(r["score"] for r in keyword)
            k_range = max_k - min_k if max_k > min_k else 1
            for r in keyword:
                nid = r["id"]
                norm_score = (r["score"] - min_k) / k_range if k_range > 0 else 1
                if nid in by_id:
                    by_id[nid]["keyword_score"] = norm_score
                else:
                    by_id[nid] = {
                        "id": nid,
                        "type": r["type"],
                        "content": r["content"],
                        "metadata": r["metadata"],
                        "vector_score": 0,
                        "keyword_score": norm_score,
                        "graph_score": 0,
                    }

        # Add graph scores
        for r in graph:
            nid = r["id"]
            if nid in by_id:
                by_id[nid]["graph_score"] = r["score"]
            else:
                by_id[nid] = {
                    "id": nid,
                    "type": r["type"],
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "vector_score": 0,
                    "keyword_score": 0,
                    "graph_score": r["score"],
                }

        # Compute combined score
        results = []
        for item in by_id.values():
            combined = (
                item["vector_score"] * self.vector_weight +
                item["keyword_score"] * self.keyword_weight +
                item["graph_score"] * self.graph_weight
            )
            item["score"] = round(combined, 4)
            item["vector_score"] = round(item["vector_score"], 4)
            item["keyword_score"] = round(item["keyword_score"], 4)
            item["graph_score"] = round(item["graph_score"], 4)
            results.append(item)

        return results
