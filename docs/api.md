# KubeMind Public API & CLI Inventory

**Source of truth:** FastAPI applications under `services/*/src/*/main.py` and Go CLI under `cmd/kmind/`.  
**Architecture:** [architecture.md](./architecture.md)

---

## Authentication, RBAC & Tenancy

Workspace is derived cryptographically from `X-API-Key` when `KUBEMIND_API_KEYS` is configured (`key:workspace:role`). In open mode (local development without keys), `X-Workspace-ID` is trusted.

### Roles & Scopes

| Role | Scope | Permitted Operations |
|------|-------|----------------------|
| **`admin`** | `*` | Full access to all endpoints, configurations, and administrative tools |
| **`developer`** | `chat`, `route`, `classify`, `mind:query`, `mind:ingest`, `usage:read` | Route prompts, dispatch completions, query memory, view usage |
| **`auditor`** | `audit:read`, `audit:verify`, `usage:read` | Read audit logs, verify SHA-256 chains, view cost analytics |
| **`viewer`** | `metrics:read`, `dashboard:read`, `usage:read` | Read-only metrics and dashboard observation |

---

## Base Service URLs

| Service | Port | Base URL | Role |
|---------|------|----------|------|
| **router** | 9080 | `http://localhost:9080` | Intent gateway, sensitivity policy, HNSW cache, cascade fallback |
| **mind** | 9081 | `http://localhost:9081` | Knowledge graph, pgvector hybrid search, fail-closed grounding |
| **agents** | 9082 | `http://localhost:9082` | Multi-step agent planner and execution runtime |
| **sentinel** | 9083 | `http://localhost:9083` | Cryptographic SHA-256 tamper-evident audit ledger & telemetry |
| **dashboard** | 9000 | `http://localhost:9000` | Next.js operator and governance dashboard |

---

## Router Service (`services/router`) — Port 9080

| Method | Path | Purpose | Request Body | Required Scope |
|--------|------|---------|--------------|----------------|
| `GET` | `/health` | Liveness + classifier/cache/auth flags | — | None |
| `GET` | `/metrics` | Prometheus metrics scrape | — | None |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat (supports non-streaming and streaming `stream: true` with de-anonymization) | `ChatRequest` | `chat` |
| `POST` | `/v1/route` | Prompt-style semantic route with explainability | `RouteRequest` | `route` |
| `POST` | `/v1/classify` | Dry-run semantic intent & policy gating (no dispatch) | `{"prompt": "..."}` | `classify` |
| `GET` | `/v1/usage/analytics` | CFO-level aggregated spend, token counts & provider distribution | `?window_hours=24` | `usage:read` |
| `GET` | `/v1/usage` | Cumulative lifetime usage summary | — | `usage:read` |
| `GET` | `/v1/intents` | List configured intents, confidence thresholds & profiles | — | None |
| `GET` | `/v1/providers/health` | Upstream provider health, latency EWMA & circuit breaker states | — | None |
| `GET` | `/v1/cache/stats` | Cache statistics, exact entry counts & HNSW vector status | — | None |
| `POST` | `/v1/cache/clear` | Clear exact & semantic cache | — | Admin key |

### Transparent Debug Response Headers

Every completion and route request returns actionable diagnostic headers:
- `X-KubeMind-Trace-ID`: Correlation ID for distributed tracing across Sentinel.
- `X-KubeMind-Intent`: Classified semantic intent.
- `X-KubeMind-Provider`: Dispatched provider backend or cache target.
- `X-KubeMind-Policy-Action`: Security verdict (`allow`, `redact`, `local_only`, `block`).
- `X-KubeMind-Cache-Hit`: `true` or `false`.
- `X-KubeMind-Fallback-Used`: `true` or `false`.
- `X-KubeMind-Latency-MS`: Total round-trip execution latency in milliseconds.

---

## Mind Service (`services/mind`) — Port 9081

| Method | Path | Purpose | Request Body | Required Scope |
|--------|------|---------|--------------|----------------|
| `GET` | `/health` | Health & database connectivity status | — | None |
| `POST` | `/v1/ingest` | Ingest document chunks or knowledge nodes | `{"content": "...", "source": "..."}` | `mind:ingest` |
| `POST` | `/v1/query` | Hybrid vector + keyword semantic search | `{"query": "...", "top_k": 4}` | `mind:query` |
| `GET` | `/v1/graph` | Inspect knowledge graph relationship topology | — | None |

---

## Sentinel Service (`services/sentinel`) — Port 9083

| Method | Path | Purpose | Request Body | Required Scope |
|--------|------|---------|--------------|----------------|
| `GET` | `/health` | Telemetry daemon health | — | None |
| `POST` | `/v1/spans` | Ingest OpenTelemetry / KubeMind trace spans | `SpanPayload` | Service key |
| `GET` | `/v1/audit/verify` | Cryptographically verify SHA-256 ledger integrity | `?workspace_id=...&limit=50` | `audit:verify` |
| `GET` | `/v1/audit/entries` | List newest audit entries with pagination | `?workspace_id=...&limit=50` | `audit:read` |
| `GET` | `/v1/stats` | System statistics (total spans, workspaces, services) | — | None |

---

## `kmind` CLI Command Reference

The compiled Go CLI (`bin/kmind`) exposes operational commands:

```bash
kmind init              # Create ~/.kmind/config.yaml
kmind up                # Start full KubeMind stack
kmind down              # Stop all services
kmind status            # Check health of all services
kmind top               # Live real-time terminal TUI cluster monitor
kmind chat [model]      # Interactive real-time streaming REPL
kmind analytics [hours] # CFO-level token usage and spend summary
kmind verify            # Cryptographically verify the SHA-256 audit ledger

kmind knowledge ingest <path|url>   # Ingest documents into Mind
kmind knowledge query "<query>"     # Search Mind knowledge graph

kmind gateway providers # Inspect upstream LLM provider circuits
kmind gateway cache-clear # Flush cache

kmind trace live        # Open browser to Observability dashboard
```
