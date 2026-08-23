# KubeMind

The reproducible quality-gate commands, measured local results, and release boundaries are documented in [docs/CI_BASELINE.md](docs/CI_BASELINE.md). Sellable SKU and forbidden claims: [docs/PRODUCT.md](docs/PRODUCT.md).

**Status:** developer preview on branch `dev`. The sold SKU is intelligent routing (Router + Mind). See [docs/PRODUCT.md](docs/PRODUCT.md). Not production-certified. Do not invoice against Compose `direct` mode.

Self-hosted AI gateway: classify prompts for purpose and sensitivity, route to an allowed model, and record the decision. Paid/production installs set `KUBEMIND_DEPLOYMENT=production` (KeyMint credentials, API keys required). Direct provider keys are laptop/migration only. Agents are preview and off in Helm.

> Product name is **KubeMind** (legacy “Tricore” / `switchboard` names are retired). See [docs/adr/0001-kubemind-naming.md](docs/adr/0001-kubemind-naming.md).

```
┌─────────────────────────────────────────────────────────────┐
│  kmind CLI  ·  Dashboard :9000  ·  landing_8 (marketing)    │
├─────────────────────────────────────────────────────────────┤
│  router   :9080  →  Intent + policy gateway + cache         │
│  mind     :9081  →  Knowledge graph + hybrid search          │
│  agents   :9082  →  Missions, planning, tools                 │
│  sentinel :9083  →  Traces + hash-chained audit ledger       │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL+pgvector · Redis · Ollama                        │
└─────────────────────────────────────────────────────────────┘
```

**Architecture deep-dive:** [docs/architecture.md](docs/architecture.md)
**Intent + governance design:** [docs/design/intent-routing.md](docs/design/intent-routing.md)

## Why it is different

| Other gateways | KubeMind |
|----------------|----------|
| Route by model name or static rules | Route by **classified intent** → full route profile |
| Observe PII/injection after the fact | **Enforce** sensitivity *before* dispatch |
| No memory service | Retrieval intents **augment from mind** |
| Mutable logs | Tamper-evident **audit ledger** |

A governance decision never depends on the intent classifier. Wrong intent costs quality; missed sensitivity is a breach.

## Quickstart

```bash
cp .env.example .env
make up
make status

# Dry-run classification (no provider call)
curl -s localhost:9080/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"why is my pod crashlooping"}'

# Partner demo: code route · retrieval · secret block · PII local_only
make demo

# Marketing site
cd landing_8 && npm install && npm run dev   # http://localhost:3000
```

Optional: set `KUBEMIND_API_KEYS=key:workspace` before exposing the stack. Open mode trusts `X-Workspace-ID` for local laptop use only.

## Architecture (services)

| Service | Host Port | Role |
|---------|-----------|------|
| **router** | 9080 | Intent classification, policy overlay, cache, providers, cascade |
| **mind** | 9081 | Knowledge ingest + hybrid query (used by retrieval intents) |
| **agents** | 9082 | Agent missions (LLM calls still go through router) |
| **sentinel** | 9083 | Spans, metrics stream, audit ledger verify |
| **Dashboard** | 9000 | Operator UI |
| **CLI** | — | `kmind` |

Full picture: **[docs/architecture.md](docs/architecture.md)**.

## Golden Rules

1. **Every LLM call** flows through **router**
2. **Every memory read/write** flows through **mind**
3. **Every execution** is traced by **sentinel**
4. **Explicit credential ownership** — KeyMint in production; direct mode only when deliberately selected
5. **Multi-tenant** — workspace from API key, never a forged header
6. **Classified before dispatched** — purpose + sensitivity before any provider

## Intent-aware routing

```bash
make eval               # held-out labelled set, consequence-weighted errors
make eval-sweep         # pick margin / abstention operating point
make eval-calibrate     # fit confidence temperature
make eval-train-linear  # ship logistic head only if it beats k-NN
make demo               # scripted partner proof
```

Configure intents and profiles in `services/router/config/gateway.yaml`. Add an intent with examples + a profile — no code.

## Deploy

```bash
# Local
make up

# Kubernetes
helm upgrade --install kubemind ./charts/kubemind \
  --namespace kubemind --create-namespace \
  --set auth.apiKeys='partner-key:acme' \
  --set auth.required=true
```

Semantic cache: Redis by default in compose; set `KUBEMIND_SEMANTIC_CACHE_BACKEND=pgvector` (Helm default) for nearest-neighbour in Postgres.

## Client SDKs & Examples

Official client SDKs with native OpenAI compatibility, offline NER pseudonymization, and tamper-evident audit verification:

- **Python SDK (`kubemind-sdk`)**: [`sdk/python/`](sdk/python) · `pip install kubemind-sdk`
- **TypeScript / Node.js SDK (`@kubemind/sdk`)**: [`sdk/typescript/`](sdk/typescript) · `npm install @kubemind/sdk`
- **Interactive Walkthroughs**: [`examples/`](examples) (Python & TypeScript demos)

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | System architecture & pipeline |
| [docs/design/intent-routing.md](docs/design/intent-routing.md) | Intent classifier + governance |
| [docs/api.md](docs/api.md) | Public API inventory |
| [docs/KUBEMIND_IMPLEMENTATION_PLAN.md](docs/KUBEMIND_IMPLEMENTATION_PLAN.md) | Phased build plan |
| [docs/adr/0001-kubemind-naming.md](docs/adr/0001-kubemind-naming.md) | Naming ADR |
| [charts/kubemind/README.md](charts/kubemind/README.md) | Helm chart |
| [landing_8/](landing_8/) | Marketing landing page |
| [quality_audit.md](quality_audit.md) | Comprehensive quality & persona audit |

## API (summary)

Full inventory: **[docs/api.md](docs/api.md)**.

### router
- `POST /v1/chat/completions` · `POST /v1/route` · `POST /v1/classify`
- `GET /v1/usage/analytics` · `GET /v1/analytics/costs` · `GET /v1/usage`
- `GET /v1/intents` · `GET /v1/routing/report` · `GET /metrics`
- Feedback review: `GET/POST /v1/intents/review*`

### mind
- `POST /v1/ingest` · `POST /v1/query` · `GET /v1/graph`

### agents
- `POST /v1/missions` · `GET /v1/missions/{id}`

### sentinel
- `POST /v1/spans` · `GET /v1/audit/verify` · `GET /v1/audit/entries` · `WS /v1/stream`

## Development

```bash
make build test lint
make down
```

## License

MIT
