# KubeMind public API inventory

**Source of truth:** FastAPI apps under `services/*/src/*/main.py`.  
**Product:** KubeMind  
**Architecture:** [architecture.md](./architecture.md)

**Auth / tenancy:** Workspace is derived from `X-API-Key` when `KUBEMIND_API_KEYS` (or config `auth.keys`) is set. In open mode (no keys), `X-Workspace-ID` is trusted for local development only. In-cluster service calls may use `KUBEMIND_SERVICE_KEY` and name a workspace in the header. See `shared/python/kubemind_auth`.

Base URLs (local compose):

| Service | Base URL |
|---------|----------|
| router | `http://localhost:9080` |
| mind | `http://localhost:9081` |
| agents | `http://localhost:9082` |
| sentinel | `http://localhost:9083` |

---

## Common conventions

| Item | Value |
|------|--------|
| Content type | `application/json` |
| API key | `X-API-Key: <key>` (binds workspace) |
| Workspace header | `X-Workspace-ID: <id>` (open mode, or service key) |
| Health | `GET /health` on every service |
| CORS | `KUBEMIND_CORS_ORIGINS` (default localhost dashboard origins) |

---

## router (`services/router`) — port 9080

Intent-aware gateway: classify → policy → profile → (retrieve) → dispatch. Service identity in `/health` is `router`.

| Method | Path | Purpose | Request summary | Auth / workspace |
|--------|------|---------|-----------------|------------------|
| `GET` | `/health` | Liveness + classifier/cache/auth flags | — | None |
| `GET` | `/metrics` | Prometheus metrics | — | None |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat; intent + policy + cache | `ChatRequest` | API key / workspace |
| `POST` | `/v1/route` | Prompt-style route API | `RouteRequest` | API key / workspace |
| `POST` | `/v1/classify` | Dry-run intent + policy (no dispatch) | `{prompt}` | API key / workspace |
| `GET` | `/v1/intents` | Configured intents → profiles | — | API key / workspace |
| `GET` | `/v1/routing/report` | Per-intent cost/latency/cache (hits = $0) | — | API key / workspace |
| `POST` | `/v1/embeddings` | Embedding via selected provider | `EmbeddingsRequest` | API key / workspace |
| `GET` | `/v1/providers/health` | Provider health + circuit state | — | API key / workspace |
| `GET` | `/v1/usage` | Per-workspace usage / cost summary | — | API key / workspace |
| `POST` | `/v1/cache/clear` | Flush Redis cache | — | Admin key required |
| `GET` | `/v1/cache/stats` | Redis stats + semantic flags | — | None |
| `POST` | `/v1/route` | Prompt-style semantic route (SDK/landing) | `RouteRequest` | `X-Workspace-ID` |

### RouteRequest (`POST /v1/route`)

```json
{
  "prompt": "Write a Go gRPC handler",
  "preferred_target": "deepseek-r1-local",
  "fallback": "vllm-local",
  "enable_cache": true,
  "max_latency_ms": 10,
  "model": "llama3.1"
}
```

**Response (summary):** `content`, `latency_ms`, `cache_hit`, `cache_type`, `provider`, `route_target`, `intent`, `usage`, optional `distance` / `similarity`.

**Cache bypass:** `enable_cache: false` or header `X-KubeMind-Cache: bypass`.

**Semantic cache:** exact Redis key first, then cosine-distance nearest neighbor (default threshold `0.05`). Design: `docs/design/semantic-cache.md`.

### ChatRequest (current)

```json
{
  "model": "llama3.1",
  "messages": [{ "role": "user", "content": "..." }],
  "temperature": 0.7,
  "max_tokens": null,
  "stream": false,
  "tools": null
}
```

### Notes

- Cache today is **exact-key** (hash of model + messages + temperature), not semantic.
- Response may include `provider`, `fallback`, `cached`.

### Phase 1 status (implemented)

| Feature | Status |
|---------|--------|
| `POST /v1/route` | **Live** |
| Semantic cache | **Live** (Redis list + cosine; Ollama embeddings) |
| Response metadata (`cache_hit`, `latency_ms`, `intent`, …) | **Live** |
| Intent classifier | **Live** (keyword heuristics) |
| Providers: `vllm`, `deepseek_local`, `anthropic` | **Configured** (need env URLs/keys) |

---

## mind (`services/mind`) — port 9081

| Method | Path | Purpose | Request summary | Auth / workspace |
|--------|------|---------|-----------------|------------------|
| `GET` | `/health` | Liveness + embedder/store ready | — | None |
| `POST` | `/v1/ingest` | Ingest URL, path, or raw content | `IngestRequest`: `source`, `type` (enum), optional `content` | `X-Workspace-ID` |
| `GET` | `/v1/nodes/{node_id}` | Node + links | path param | `X-Workspace-ID` |
| `POST` | `/v1/query` | Hybrid search (vector + keyword + graph) | `QueryRequest`: `query`, optional `filters`, `top_k` | `X-Workspace-ID` |
| `POST` | `/v1/memory/query` | **Alias** of `/v1/query` (landing/SDK) | same as QueryRequest | `X-Workspace-ID` |
| `POST` | `/v1/link` | Explicit link between nodes | `LinkRequest`: `source_id`, `target_id`, `link_type` | `X-Workspace-ID` |
| `GET` | `/v1/graph` | Export workspace subgraph | — | `X-Workspace-ID` |
| `GET` | `/v1/types` | Supported node types + field hints | — | None |

### NodeType enum

`document` · `code` · `conversation` · `agent_memory` · `plan`

### QueryRequest (current)

```json
{
  "query": "mTLS requirements",
  "filters": { "type": "document" },
  "top_k": 10
}
```

### Phase 2 status (implemented)

| Feature | Status |
|---------|--------|
| `POST /v1/memory/query` | **Live** (alias of `/v1/query`) |
| pgvector + HNSW | **Supported** when DB image has extension (`pgvector/pgvector:pg16`) |
| JSON embedding fallback | **Live** if extension unavailable |
| Document chunking | **Live** (`chunking` in `knowledge.yaml`) |
| Backend interface | **Live** (`backends/`; default pgvector) |

---

## agents (`services/agents`) — port 9082

| Method | Path | Purpose | Request summary | Auth / workspace |
|--------|------|---------|-----------------|------------------|
| `GET` | `/health` | Liveness + tools/engine flags | — | None |
| `POST` | `/v1/missions` | Create + run mission (`sync` or `async`) | `MissionRequest`: `prompt`, `mode`, optional `model`, `tools`, `max_steps` | `X-Workspace-ID` |
| `GET` | `/v1/missions/{mission_id}` | Mission status | path param | `X-Workspace-ID` |
| `POST` | `/v1/missions/{mission_id}/cancel` | Cancel mission | path param | `X-Workspace-ID` |
| `GET` | `/v1/missions` | List missions | query `limit` (default 50) | `X-Workspace-ID` |
| `POST` | `/v1/tools/invoke` | Invoke a single tool | `ToolInvokeRequest`: `tool`, `arguments` | `X-Workspace-ID` |
| `GET` | `/v1/tools` | List tool schemas | — | None |

### MissionRequest (current)

```json
{
  "prompt": "Write a factorial function",
  "mode": "sync",
  "model": null,
  "tools": null,
  "max_steps": 20
}
```

### Planned compatibility aliases (not implemented yet)

| Method | Path | Phase | Maps to |
|--------|------|-------|---------|
| `POST` | `/v1/task/dispatch` | 4 | Mission create/run |
| `POST` | `/v1/missions/{id}/approve` | 4 | HITL |
| `POST` | `/v1/missions/{id}/reject` | 4 | HITL |
| — | K8s tools | 4 | Tool registry |

---

## sentinel (`services/sentinel`) — port 9083

Spans for observability; hash-chained **audit ledger** for proof. Workspace reads are scoped to the authenticated key.

| Method | Path | Purpose | Request summary | Auth / workspace |
|--------|------|---------|-----------------|------------------|
| `GET` | `/health` | Liveness + span/WS/ledger flags | — | None |
| `POST` | `/v1/spans` | Ingest one span (+ ledger append) | `SpanIngest` | API key / workspace |
| `POST` | `/v1/spans/query` | Query spans (rich filters) | `SpanQuery` | API key / workspace |
| `GET` | `/v1/spans` | Query spans | query params | API key / workspace |
| `GET` | `/v1/audit/verify` | Walk hash chain; report first break | `workspace_id`, `limit` | API key / workspace |
| `GET` | `/v1/audit/head` | Current head hash for external anchoring | `workspace_id` | API key / workspace |
| `GET` | `/v1/audit/entries` | List ledger entries | `workspace_id`, `limit`, `offset` | API key / workspace |
| `GET` | `/v1/audit/retention` | Retention + legal hold | `workspace_id` | API key / workspace |
| `GET` | `/v1/metrics` | Aggregated metrics | `workspace_id`, `hours` | API key / workspace |
| `GET` | `/v1/export` | Export traces (+ redaction summary) | `workspace_id` | API key / workspace |
| `GET` | `/metrics` | Prometheus text exposition | — | None |
| `WS` | `/v1/stream` | Real-time span stream | `subscribe`, `ping` | Message / key |

### SpanIngest (current)

```json
{
  "trace_id": "...",
  "span_id": "...",
  "parent_id": null,
  "workspace_id": "default",
  "service": "router",
  "operation": "llm_call",
  "start_time": "2026-07-26T00:00:00Z",
  "end_time": null,
  "status": "ok",
  "attributes": {}
}
```

### WebSocket client messages

```json
{ "type": "subscribe", "workspace_id": "default" }
{ "type": "ping" }
```

### Phase 3 status (implemented)

| Feature | Status |
|---------|--------|
| PII / secret redaction on ingest | **Live** (email, phone, aws_key, bearer, private_key, api_key) |
| Injection scoring | **Live** (`injection_score`, `injection_flags` on attributes) |
| `GET /metrics` | **Live** Prometheus counters |
| `GET /v1/telemetry/traces` | **Live** alias of `/v1/spans` |
| Export checksum + redaction summary | **Live** |
| OTLP export | **Optional** via `OTEL_EXPORTER_OTLP_ENDPOINT` |

### Note on `beacon_trace`

`services/sentinel/src/beacon_trace/` is a legacy/alternate package path. Canonical service is **sentinel**. New code must not expand `beacon_trace`.

---

## Inter-service URLs (compose defaults)

| From | Env var | Default |
|------|---------|---------|
| agents → router | `ROUTER_URL` | `http://router:8080` |
| agents → mind | `MIND_URL` | `http://mind:8081` |
| agents → sentinel | `SENTINEL_URL` | `http://sentinel:8083` |
| * → Postgres | `DATABASE_URL` | `postgresql://tricore:tricore@postgres:5432/tricore` |
| router → Redis | `REDIS_URL` | `redis://redis:6379/0` |
| * → Ollama | `OLLAMA_BASE_URL` | `http://ollama:11434` |

DB user/db name `tricore` is a **compose legacy string**, not the product name. Renaming DB credentials is optional and out of Phase 0.

---

## OpenAPI

Each service exposes FastAPI auto-docs when running:

- `http://localhost:9080/docs`
- `http://localhost:9081/docs`
- `http://localhost:9082/docs`
- `http://localhost:9083/docs`

This markdown inventory is the human-readable Phase 0 snapshot; regenerate or diff against `/openapi.json` when routes change.
