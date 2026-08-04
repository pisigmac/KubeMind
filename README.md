# KubeMind

**Kubernetes-native AI operating infrastructure** — self-hosted control plane for LLM routing, hybrid knowledge memory, agents, and trace observability.

> **Note:** The repository directory may still be named `tricore` on disk. The **product name is KubeMind**. See [docs/adr/0001-kubemind-naming.md](docs/adr/0001-kubemind-naming.md).

```
┌─────────────────────────────────────────────────────────────┐
│  kmind CLI  |  Next.js Dashboard (port 9000)               │
├─────────────────────────────────────────────────────────────┤
│  router   :9080  →  LLM gateway + cache + circuit breaker  │
│  mind     :9081  →  Knowledge graph + hybrid search          │
│  agents   :9082  →  Agent engine + planning + tools          │
│  sentinel :9083  →  Observability + WebSocket streaming      │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL (:9432) | Redis (:9379) | Ollama (:9434)         │
└─────────────────────────────────────────────────────────────┘
```

**Target K8s namespace:** `kubemind-system` (Helm chart in progress — see implementation plan).

## Quickstart

```bash
# 1. Clone and configure
git clone https://github.com/pisigmac/tricore.git
cd tricore
cp .env.example .env
# Edit .env — add free-tier API keys if you have them

# 2. Start everything
make up

# 3. Verify
make status

# 4. Build CLI and run your first agent mission
make cli
./bin/kmind agent run "Write a Python function to calculate factorial"

# 5. Open dashboard
open http://localhost:9000
```

## Architecture

| Service | Host Port | Internal Port | Role | Language |
|---------|-----------|---------------|------|----------|
| **router** | 9080 | 8080 | LLM gateway, routing, caching, cost tracking, circuit breaker | Python 3.12 |
| **mind** | 9081 | 8081 | Knowledge graph, embeddings, hybrid search, link detection | Python 3.12 |
| **agents** | 9082 | 8082 | Agent execution, planning, tools, memory | Python 3.12 |
| **sentinel** | 9083 | 8083 | Observability, tracing, WebSocket streaming, metrics | Python 3.12 |
| **Dashboard** | 9000 | 3000 | Next.js web UI with real-time data | TypeScript |
| **CLI** | — | — | Go binary **`kmind`** for stack control | Go 1.22 |

## Golden Rules

1. **Every LLM call** flows through **router**
2. **Every memory read/write** flows through **mind**
3. **Every execution** is traced by **sentinel**
4. **Local-first** — works offline with Ollama
5. **Multi-tenant** — workspace derived from an API key, never a client header
6. **Classified before dispatched** — every prompt is scored for purpose
   (intent) and for sensitivity (PII, secrets, injection) before it is sent
   anywhere. A governance decision never depends on the intent classifier.

## Intent-aware routing

The router picks a **route profile** from the classified intent — model,
provider pool, parameters, system prompt, cache policy and whether to retrieve
from `mind` — then narrows the eligible pool with a sensitivity verdict.

```bash
# See the decision without paying for a completion
curl -s localhost:9080/v1/classify -d '{"prompt":"why is my pod crashlooping"}'

make eval          # score the classifier against a held-out labelled set
make eval-sweep    # accuracy versus abstention across thresholds
```

A prompt containing personal data is forced onto a local provider, and refused
outright if none is healthy rather than falling back to a cloud provider. A
prompt containing a private key is blocked before dispatch.

Full design: **[docs/design/intent-routing.md](docs/design/intent-routing.md)**.

## Inter-Service Communication

```
router → sentinel (LLM call spans)
mind → sentinel (ingest/query spans)
agents → router (all LLM calls)
agents → mind (memory read/write)
agents → sentinel (plan/tool spans)
Dashboard → all services (REST + WebSocket on sentinel)
CLI → all services (HTTP)
```

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/KUBEMIND_IMPLEMENTATION_PLAN.md](docs/KUBEMIND_IMPLEMENTATION_PLAN.md) | Phased build plan (landing → code gaps) |
| [docs/adr/0001-kubemind-naming.md](docs/adr/0001-kubemind-naming.md) | Product naming decision |
| [docs/api.md](docs/api.md) | Public API inventory |
| [docs/migration/legacy-k8s.md](docs/migration/legacy-k8s.md) | Old K8s names → KubeMind |
| [shared/schemas/](shared/schemas/) | JSON Schema contracts for SDKs |

## Development

```bash
make build              # Build all services + CLI
make test               # Run all test suites
make test-integration   # Integration tests (requires stack)
make lint               # ruff, mypy, go vet, next lint
make down               # Stop all services
make status             # Health of all services
```

## API Reference (summary)

Full inventory: **[docs/api.md](docs/api.md)**.

### router
- `POST /v1/chat/completions` — OpenAI-compatible chat + semantic/exact cache
- `POST /v1/route` — Prompt-style route API (SDK/landing; returns `cache_hit`, `latency_ms`, `intent`)
- `POST /v1/classify` — Dry-run intent + policy for a prompt, without dispatching
- `GET /v1/intents` — Configured intents and the profile each resolves to
- `GET /v1/routing/report` — Per-intent cost, latency, cache hit rate, egress class
- `POST /v1/embeddings` — Embedding requests
- `GET /v1/providers/health` — Provider status + circuit state
- `GET /v1/usage` — Per-workspace cost/token analytics
- `GET /metrics` — Prometheus scrape
- `POST /v1/cache/clear` — Clear Redis cache (admin key required)

### mind
- `POST /v1/ingest` — Ingest URL, file, or content (chunked)
- `POST /v1/query` — Hybrid search (vector + keyword + graph)
- `POST /v1/memory/query` — Alias of `/v1/query` (SDK/landing)
- `GET /v1/nodes/{id}` — Get node with links
- `GET /v1/graph` — Export subgraph

### agents
- `POST /v1/missions` — Create and run a mission
- `GET /v1/missions/{id}` — Mission status
- `GET /v1/missions` — List missions
- `POST /v1/tools/invoke` — Invoke a tool

### sentinel
- `POST /v1/spans` — Ingest a trace span
- `GET /v1/spans` — Query spans
- `GET /v1/metrics` — Aggregated metrics
- `GET /v1/export` — Export traces
- `WS /v1/stream` — Real-time stream

## License

MIT
