# Semantic cache design (router)

**Phase:** 1  
**Status:** Implemented (MVP)  
**Service:** router  

## Goals

- Return near-duplicate prompts from cache without calling an LLM  
- Expose `cache_hit`, `cache_type`, `distance` / `similarity`, `latency_ms` on responses  
- Keep exact-key Redis cache as a fast first path  

## Embedding source

| Item | Value |
|------|--------|
| Default model | `nomic-embed-text` via Ollama |
| Env | `OLLAMA_BASE_URL` (default `http://localhost:11434` / compose `http://ollama:11434`) |
| Config | `cache.semantic.embedding_model` in `gateway.yaml` |

On embed failure: semantic cache is skipped (exact cache still works).

## Distance metric

- **Cosine distance** = `1 - cosine_similarity`  
- **Hit** when `distance <= cache.semantic.distance_threshold`  
- Default threshold: **`0.05`** (≈ similarity ≥ 0.95)

## Storage (MVP)

Redis list per workspace:

```text
key: km:sem:{workspace_id}
value: JSON entries { embedding, response, model, prompt_preview, created_at }
```

- Cap: `max_entries_per_workspace` (default 10_000); LPUSH + LTRIM  
- TTL: entry-level not per-key; list refreshed by TTL on key via EXPIRE = `cache.ttl_seconds`  
- Search: load up to N recent entries (default same cap, scan capped at 2000 for latency), nearest neighbor in process  

**Why not RediSearch first:** works with stock Redis 7 in compose without Redis Stack.

**Upgrade path:** Redis Stack vector index or Postgres pgvector table `router_semantic_cache`.

## Lookup order

1. Exact SHA-256 key cache (`km:exact:…`)  
2. Semantic nearest neighbor (if enabled)  
3. Provider call → write exact + semantic  

## Bypass

- Body: `enable_cache: false` on `/v1/route`  
- Header: `X-KubeMind-Cache: bypass`  

## Response metadata

```json
{
  "cache_hit": true,
  "cache_type": "semantic",
  "distance": 0.02,
  "similarity": 0.98,
  "latency_ms": 3.1,
  "provider": "cache",
  "route_target": "cache/semantic",
  "intent": "code"
}
```

## Config (`gateway.yaml`)

```yaml
cache:
  backend: redis
  ttl_seconds: 300
  exact_match: true
  semantic:
    enabled: true
    embedding_model: nomic-embed-text
    distance_threshold: 0.05
    max_entries_per_workspace: 10000
    scan_limit: 2000
```
