# KubeMind Implementation Plan

**Canonical product name:** KubeMind (formerly dual-branded as Tricore)  
**Repo path:** `/home/oh20210736-ud/Documents/WorkSpace/tricore`  
**Landing reference:** `landing_7` (marketing claims)  
**Status:** Living plan — implement capability track; keep marketing honest until each exit criterion is met  
**Last updated:** 2026-07-26

---

## 1. Purpose

This document is the **source-of-truth build plan** for bringing the real backend/platform up to the capabilities advertised on the KubeMind landing page.

It answers:

1. Which services already exist?
2. What landing claims are incomplete or false today?
3. Exactly what to build, in what order, with acceptance criteria?

**Decision locked:** Product is **KubeMind** going forward.

| Concept | Canonical value |
|---------|-----------------|
| Product name | KubeMind |
| K8s namespace | `kubemind-system` |
| Helm release / chart | `kubemind` / `charts/kubemind` |
| Image registry prefix | `kubemind/` (or org-owned equivalent) |
| CLI (canonical) | **`kmind`** (`bin/kmind`; optional `tricore` symlink for one release) |
| Public host ports | `9080` router · `9081` mind · `9082` agents · `9083` sentinel · `9000` dashboard |

Legacy names to retire: `tricore` namespace, `switchboard`, `contextweave`, `deepagents`, `tracer`, `SwitchBoard` log prefixes.

---

## 2. Current inventory (codebase fact)

### 2.1 Services that exist

| Service | Port | Path | Language | Role today |
|---------|------|------|----------|------------|
| **router** | 9080 | `services/router` | Python FastAPI | LLM gateway, exact Redis cache, circuit breaker, rate limit, usage |
| **mind** | 9081 | `services/mind` | Python FastAPI | Knowledge ingest, hybrid search (vector+keyword+graph), embeddings |
| **agents** | 9082 | `services/agents` | Python FastAPI | Mission planner + tools (fs/shell/web/knowledge) |
| **sentinel** | 9083 | `services/sentinel` | Python FastAPI | Span store (SQLite), metrics, WebSocket stream |
| **dashboard** | 9000 | `dashboard/` | Next.js | Operator UI |
| **CLI** | — | `cmd/tricore` | Go | Stack control (`tricore` binary) |

Compose stack (`docker-compose.yml`): Postgres `:9432`, Redis `:9379`, Ollama `:9434`, all four services + dashboard.

### 2.2 What already works (do not rebuild)

- Router: `POST /v1/chat/completions`, `POST /v1/embeddings`, provider health, usage, cache clear/stats
- Mind: `POST /v1/ingest`, `POST /v1/query`, `GET /v1/graph`, workspace scoping, connectors (doc/git/web)
- Agents: `POST /v1/missions`, tools invoke, planner loop calling router/mind/sentinel
- Sentinel: `POST /v1/spans`, query, metrics, export, `WS /v1/stream`
- Local-first Ollama path in compose
- Unit tests under each service’s `tests/`

### 2.3 Critical gaps vs landing

| Landing claim | Code reality | Severity |
|---------------|--------------|----------|
| Semantic cache &lt;4ms | Exact-key Redis only | **P0** |
| `POST /v1/route` | Missing (use chat completions) | **P0** |
| Intent classification | Missing | P1 |
| DeepSeek-R1 / vLLM providers | Missing | P1 |
| Real pgvector HNSW | JSON embeddings; optional extension try | P1 |
| `POST /v1/memory/query` | Missing alias | P1 |
| K8s autonomous agents / OPA / Temporal | Generic tools only | P1 |
| `POST /v1/task/dispatch` | Missing alias | P1 |
| PII redaction / injection scoring | Missing | P1 |
| Prometheus / OTLP | Missing | P1 |
| Helm chart | Missing entirely | **P0** for deploy story |
| K8s manifests | Stale names (`switchboard`…) | P0 for deploy |
| Python/Go/TS SDKs | Missing | P1 |
| mTLS / SPIFFE / Envoy | Missing | P2 |
| ClickHouse / eBPF / Rust rewrite | Missing | P2 / non-goal MVP |
| Product naming consistency | Tricore everywhere | P0 hygiene |

---

## 3. Strategy

**Track A — Capability (this plan):** Implement features in phases below under KubeMind naming.

**Track B — Truth (ongoing):** Do not advertise Rust/gRPC/Temporal/ClickHouse/eBPF until real. Prefer landing tech labels: Python, FastAPI, Postgres, Redis, Ollama/vLLM, Helm.

**MVP definition of “landing-credible”:**

1. Semantic cache path works end-to-end  
2. Landing API aliases exist  
3. `helm install kubemind` brings up healthy control plane  
4. At least one SDK (`python`) works against local stack  
5. Basic PII redaction + Prometheus metrics on sentinel  
6. Agents can read Kubernetes resources (list/logs)

---

## 4. Phase 0 — KubeMind identity freeze

**Duration:** 0.5–1 day  
**Owner:** platform  
**Depends on:** nothing  

### Goals

Lock naming, document public APIs, freeze legacy paths for rewrite.

### Tasks (detailed)

#### T0.1 — Write identity ADR

**File:** `docs/adr/0001-kubemind-naming.md`

Content must include:

- Product name KubeMind
- Namespace `kubemind-system`
- Service DNS: `router.kubemind-system.svc`, etc.
- Env var prefix migration: prefer `KUBEMIND_*`, accept `TRICORE_*` / legacy for one release
- Image names: `kubemind/router`, `kubemind/mind`, `kubemind/agents`, `kubemind/sentinel`, `kubemind/dashboard`
- CLI: **`kmind`** entrypoint; `tricore` may remain a symlink for 1 release

**Acceptance:** ADR merged; README title section references KubeMind.

#### T0.2 — API inventory from live FastAPI apps

**File:** `docs/api.md`

For each service, document:

| Method | Path | Purpose | Request body summary | Auth header |
|--------|------|---------|----------------------|-------------|
| … | … | … | … | `X-Workspace-Id` or equivalent |

Generate by reading:

- `services/router/src/router/main.py`
- `services/mind/src/mind/main.py`
- `services/agents/src/agents/main.py`
- `services/sentinel/src/sentinel/main.py`

Also list **planned aliases** (Phase 1–4) in a separate “Compatibility” section.

**Acceptance:** `docs/api.md` lists every existing route with path accuracy.

#### T0.3 — Shared schemas decision

**Dir:** `shared/schemas/` (currently empty)

Decide and document:

- Format: OpenAPI 3.1 fragments **or** JSON Schema files per resource (`route-request.json`, `span.json`, `mission.json`)
- Ownership: router owns route/chat schemas; mind owns node/query; agents owns mission; sentinel owns span
- CI later validates SDKs against schemas (Phase 6)

**Acceptance:** At least skeleton files + `shared/schemas/README.md` describing process.

#### T0.4 — Deprecation list for legacy K8s

**File:** `docs/migration/legacy-k8s.md`

Map:

| Legacy (`k8s/`) | KubeMind target |
|-----------------|-----------------|
| `switchboard` | `router` |
| `contextweave` | `mind` |
| `deepagents` | `agents` |
| `tracer` | `sentinel` |
| namespace `tricore` | `kubemind-system` |

**Acceptance:** Document exists; Phase 5 tasks reference it.

#### T0.5 — README dual-name cleanup (minimal)

Update top of `README.md`:

- Title: KubeMind
- Architecture diagram labels: router/mind/agents/sentinel
- Note: “Repository directory may still be named tricore; product is KubeMind.”

**Acceptance:** New contributor can identify product as KubeMind from README alone.

### Phase 0 exit criteria

- [x] ADR 0001 written (`docs/adr/0001-kubemind-naming.md`)  
- [x] `docs/api.md` complete for current routes  
- [x] `shared/schemas/README.md` + JSON Schema skeletons present  
- [x] Legacy K8s map written (`docs/migration/legacy-k8s.md`)  
- [x] README identifies KubeMind  

**Phase 0 completed:** 2026-07-26  


---

## 5. Phase 1 — Router: semantic routing & providers

**Duration:** 1–2 weeks  
**Path:** `services/router`  
**Depends on:** Phase 0 (naming/env conventions)  

### Goals

Make router match “semantic prompt router” landing story without rewriting in Rust.

### Tasks (detailed)

#### T1.1 — Semantic cache design spike (0.5 day)

**Deliverable:** short design note in `docs/design/semantic-cache.md`

Decide:

1. **Embedding source:** Ollama `nomic-embed-text` via `OLLAMA_BASE_URL` (default)  
2. **Index store:**  
   - Preferred MVP: Redis + cosine search over a capped in-memory/Redis list of vectors **or** Redis Stack RediSearch if available  
   - Fallback: Postgres pgvector table `router_semantic_cache` if Redis vectors too weak  
3. **Key payload:** `{ embedding, response_json, model, workspace_id, created_at, prompt_hash }`  
4. **Threshold:** config `cache.semantic_distance_threshold` default `0.05` (cosine distance) or similarity `0.95` — pick one and document  
5. **TTL:** reuse `cache.ttl_seconds` from `gateway.yaml`  
6. **Bypass:** header `X-KubeMind-Cache: bypass` or body flag `enable_cache: false`

**Acceptance:** Design note checked in; threshold semantics unambiguous.

#### T1.2 — Implement `SemanticCache` module

**Files:**

- `services/router/src/router/cache/semantic.py` (new)
- `services/router/src/router/cache/manager.py` (keep exact cache; compose both)
- `services/router/config/gateway.yaml` — extend `cache:` block:

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
```

**Behavior:**

1. On chat/route request, embed last user message (or full prompt string)  
2. Query nearest neighbor within workspace  
3. If distance ≤ threshold → return cached response with `cache_hit: true`, `cache_type: "semantic"`, `similarity`/`distance`, `latency_ms`  
4. Else exact-key cache check (existing)  
5. On miss, call provider; store exact + semantic entries  

**Acceptance:**

- Unit tests in `services/router/tests/test_semantic_cache.py` for distance hit/miss  
- Integration test (optional mark) with live Ollama  

#### T1.3 — Response metadata enrichment

Every chat/route response must include:

```json
{
  "provider": "ollama",
  "fallback": false,
  "cache_hit": false,
  "cache_type": null,
  "latency_ms": 12.4,
  "route_target": "ollama/llama3.1",
  "intent": "general"
}
```

**Files:** `services/router/src/router/main.py`, models if needed.

**Acceptance:** Contract documented in `docs/api.md`; tests assert keys present.

#### T1.4 — Intent classification (lightweight)

**File:** `services/router/src/router/intent.py`

MVP approach (choose one, document in code):

- **A (fast):** keyword/heuristic + optional embedding centroid labels for `code | rag | security | log | general`  
- **B (better):** small classify prompt to local model only when heuristics uncertain  

Config in `gateway.yaml`:

```yaml
routing:
  intent_enabled: true
  prefer_targets:
    code: deepseek-r1-local
    rag: ollama
    security: ollama
    log: vllm-local
    general: ollama
```

**Acceptance:** Intent appears in response metadata; prefer_targets influences provider selection when target healthy.

#### T1.5 — Provider additions

**Files:**

- `services/router/config/gateway.yaml`
- `services/router/src/router/providers/` (reuse `openai_compat.py` where possible)

Add configs:

| Provider name | Type | Notes |
|---------------|------|--------|
| `vllm` | OpenAI-compatible | `VLLM_BASE_URL`, models list |
| `deepseek_local` | Ollama or vLLM | model tag e.g. `deepseek-r1` |
| `anthropic` | native or compat proxy | `ANTHROPIC_API_KEY` |

Skip registration when env URL/key missing (same pattern as current providers).

**Acceptance:** With env set, `/v1/providers/health` lists new providers; chat can target model string.

#### T1.6 — API alias `POST /v1/route`

**Contract (landing/SDK oriented):**

```http
POST /v1/route
Content-Type: application/json
X-Workspace-Id: default

{
  "prompt": "string",
  "preferred_target": "deepseek-r1-local",
  "fallback": "vllm-cluster",
  "enable_cache": true,
  "max_latency_ms": 10,
  "model": "optional-override"
}
```

Implementation:

1. Map `prompt` → OpenAI-style `messages: [{role:user, content:prompt}]`  
2. Apply preferred_target → provider/model resolution  
3. Call same pipeline as chat completions (semantic cache, rate limit, usage)  
4. Return unified body: `{ content, latency_ms, cache_hit, provider, route_target, usage }`  

Keep `POST /v1/chat/completions` as primary OpenAI-compatible path.

**Acceptance:** Curl against compose hits `/v1/route` successfully; OpenAPI/docs updated.

#### T1.7 — Tests & observability hooks

- Unit: semantic threshold, intent mapping, route request validation  
- Emit span to sentinel (existing `TracerClient`) with `cache_hit`, `intent`, `provider` attributes  
- Rename log prefix `SwitchBoard` → `router` / `KubeMind`

**Acceptance:** `cd services/router && pytest tests/ -v` green.

### Phase 1 exit criteria

- [x] Semantic cache hit path implemented (unit tests for cosine/hit/miss)  
- [x] `/v1/route` live  
- [x] Metadata includes `cache_hit`, `latency_ms`, `intent`, `route_target`  
- [x] vLLM / DeepSeek / Anthropic configurable in `gateway.yaml`  
- [x] Unit tests for semantic cache + intent  

**Phase 1 completed:** 2026-07-26  

**Note:** End-to-end semantic hit against live Ollama requires `make up` + `nomic-embed-text` pulled.  


---

## 6. Phase 2 — Mind: vector store hardening

**Duration:** 1–1.5 weeks  
**Path:** `services/mind`  
**Depends on:** Phase 0  

### Goals

Production-credible hybrid memory with real pgvector and landing API alias.

### Tasks (detailed)

#### T2.1 — Postgres + pgvector as first-class

**Files:** `services/mind/src/mind/storage.py`, Dockerfile/compose notes

1. Ensure compose Postgres image supports pgvector **or** switch to `pgvector/pgvector:pg16`  
2. On init: `CREATE EXTENSION IF NOT EXISTS vector` must succeed in dev compose (fail loud if not)  
3. Migration:  
   - Add `embedding_vec vector(768)` (or configurable dims)  
   - Backfill from JSON `embedding` if present  
   - Create HNSW index: `CREATE INDEX ... USING hnsw (embedding_vec vector_cosine_ops)`  
4. `search_by_vector` uses `<=>` / cosine distance SQL, filtered by `workspace_id`

**Acceptance:** Integration test inserts nodes and retrieves via vector distance; index used (EXPLAIN optional).

#### T2.2 — Chunking config

**File:** `services/mind/config/knowledge.yaml`

```yaml
chunking:
  max_tokens: 512
  overlap_tokens: 64
  strategy: recursive_character
```

Wire into document connector ingest path.

**Acceptance:** Large document ingest creates multiple nodes with stable parent metadata.

#### T2.3 — API alias `POST /v1/memory/query`

Map to existing query pipeline; accept body:

```json
{
  "query": "...",
  "top_k": 10,
  "filters": { "type": "doc" }
}
```

Response shape stable and documented.

Also keep `POST /v1/query`.

**Acceptance:** Both paths return equivalent results.

#### T2.4 — Tenant isolation audit

Review all store methods: every query must include `workspace_id`. Add tests for cross-workspace leakage (must return empty).

**Acceptance:** Dedicated test proves isolation.

#### T2.5 — Backends stubs (non-blocking)

Under `services/mind/src/mind/backends/`:

- `base.py` interface: `upsert`, `search`, `delete`  
- `pgvector.py` implements  
- Placeholder modules `milvus.py`, `neo4j.py` raising `NotImplementedError` with README note  

**Acceptance:** Interface exists; default backend is pgvector.

### Phase 2 exit criteria

- [x] pgvector image + HNSW in default compose (`pgvector/pgvector:pg16`)  
- [x] `/v1/memory/query` works  
- [x] Isolation + chunking unit tests pass  
- [x] Chunking configurable  

**Phase 2 completed:** 2026-07-26  

**Note:** Existing Postgres volumes created with `postgres:16-alpine` need `docker compose down -v` once to recreate with pgvector.  


---

## 7. Phase 3 — Sentinel: security & observability

**Duration:** 1.5–2 weeks  
**Path:** `services/sentinel` (+ optional router pre-hook)  
**Depends on:** Phase 0  

### Goals

Earn Security grid claims with pragmatic controls (not eBPF/ClickHouse yet).

### Tasks (detailed)

#### T3.1 — PII / secret redaction

**Files:**

- `services/sentinel/src/sentinel/redaction.py`  
- Apply in span ingest path before persistence  

Patterns (v1):

- Email, phone  
- AWS keys, generic API key shapes  
- Bearer tokens, private key headers  
- Credit card Luhn-optional simple regex  

Store both:

- Redacted attributes in primary span  
- Optional `attributes_redacted_fields: ["email", ...]` list  

Config: `services/sentinel/config/trace.yaml`

```yaml
redaction:
  enabled: true
  modes: [email, phone, aws_key, bearer, private_key]
```

**Acceptance:** Unit tests with sample payloads; no raw secret in SQLite after ingest.

#### T3.2 — Prompt injection heuristics

**File:** `services/sentinel/src/sentinel/guardrails.py`

Score 0.0–1.0 from rules (ignore previous instructions, exfiltrate system prompt, etc.).

Attach to span attributes: `injection_score`, `injection_flags[]`.

Optional: router calls sentinel or local shared lib before dispatch (feature flag).

**Acceptance:** Known bad prompts score above threshold; benign prompts low.

#### T3.3 — Prometheus metrics

**Endpoint:** `GET /metrics` (Prometheus text format)

Metrics:

- `kubemind_spans_ingested_total{service,status}`  
- `kubemind_span_duration_ms_bucket` (or summary)  
- `kubemind_websocket_connections`  
- `kubemind_redactions_total`  

**Acceptance:** Prometheus can scrape; smoke test greps metric names.

#### T3.4 — OTLP export (optional config)

When `OTEL_EXPORTER_OTLP_ENDPOINT` set, export spans via OTLP HTTP.

When unset, no-op.

**Acceptance:** Documented env; no crash when unset.

#### T3.5 — API alias `GET /v1/telemetry/traces`

Alias of span query with same filters (`workspace_id`, `service`, time range).

**Acceptance:** Documented; parity with `/v1/spans`.

#### T3.6 — Audit export enrichment

Enhance `/v1/export`:

- Include redaction metadata  
- Stable ordering by time  
- Optional signed checksum file for export batch (simple SHA256 manifest)

**Acceptance:** Export JSON includes redaction flags.

### Phase 3 exit criteria

- [x] Redaction on by default  
- [x] Injection score on spans  
- [x] `/metrics` live  
- [x] `/v1/telemetry/traces` alias  
- [x] Unit tests + curl tests in `tests.md`  

**Phase 3 completed:** 2026-07-26  

**Explicit non-goals this phase:** ClickHouse migration, eBPF, full SOC2 certification.

**Manual / curl tests:** see root [`tests.md`](../tests.md).

---

## 8. Phase 4 — Agents: Kubernetes-aware capabilities

**Duration:** 2 weeks  
**Path:** `services/agents`  
**Depends on:** Phase 0; optional Phase 3 for audit spans  

### Goals

Earn “K8s agents” claim with real cluster tools + HITL for mutations — **not** a full Temporal/operator rewrite.

### Tasks (detailed)

#### T4.1 — Kubernetes client integration

**Dependency:** `kubernetes` Python client in `requirements.txt`

**Config:**

- In-cluster: ServiceAccount  
- Local: `KUBECONFIG` env  

**Tools to add** in `services/agents/src/agents/tools.py` (or `tools/k8s.py`):

| Tool | Verb | Mutating? |
|------|------|-----------|
| `k8s_get` | get/list resources | No |
| `k8s_describe` | describe-like events+status | No |
| `k8s_logs` | pod logs | No |
| `k8s_scale` | scale deployment | **Yes** |
| `k8s_apply_dry_run` | dry-run apply | No (dry-run) |

RBAC: document minimal ClusterRole for read-only default; mutating role optional.

**Acceptance:** Integration test against kind/minikube or mocked client; mission can list pods in `kubemind-system`.

#### T4.2 — Human-in-the-loop gate

**Mission model fields:**

- `requires_approval: bool`  
- `approval_status: pending|approved|rejected|not_required`  
- `pending_actions: []`  

**API:**

- `POST /v1/missions/{id}/approve`  
- `POST /v1/missions/{id}/reject`  

Mutating tools refuse to run until approved when `human_in_the_loop: true` on create.

**Acceptance:** Test that scale is blocked until approve.

#### T4.3 — Simple plan DAG

Planner outputs steps with `id`, `depends_on[]`, `tool`, `args`.

Engine executes in topological order; fail-fast on dependency failure; persist plan on mission record.

**Acceptance:** Multi-step mission with dependency runs in order; stored plan visible in GET mission.

#### T4.4 — API alias `POST /v1/task/dispatch`

Maps to mission create/run:

```json
{
  "prompt": "...",
  "human_in_the_loop": true,
  "namespace": "kubemind-system"
}
```

Keep `/v1/missions` as primary.

**Acceptance:** Alias documented and tested.

#### T4.5 — Docs honesty

**File:** `docs/agents/k8s-scope.md`

State clearly:

- Implemented: tools + HITL + simple DAG  
- Not implemented: controller-runtime operator, Temporal, OPA sidecar, automatic pod healing loops  

**Acceptance:** Doc linked from README.

### Phase 4 exit criteria

- [ ] Read tools work against a cluster  
- [ ] HITL blocks mutations  
- [ ] `/v1/task/dispatch` alias  
- [ ] Scope doc published  

---

## 9. Phase 5 — Helm chart & K8s rename

**Duration:** 1–1.5 weeks  
**Path:** `charts/kubemind/`, rewrite `k8s/`  
**Depends on:** Phase 0; images buildable  

### Goals

Make `helm install kubemind kubemind/kubemind -n kubemind-system` real.

### Tasks (detailed)

#### T5.1 — Chart scaffolding

```text
charts/kubemind/
  Chart.yaml
  values.yaml
  templates/
    namespace.yaml          # optional
    router-deployment.yaml
    router-service.yaml
    mind-deployment.yaml
    mind-service.yaml
    agents-deployment.yaml
    agents-service.yaml
    sentinel-deployment.yaml
    sentinel-service.yaml
    dashboard-*.yaml
    postgres.yaml           # or external
    redis.yaml
    configmap.yaml
    secrets.yaml
    hpa-router.yaml
    serviceaccount.yaml
    networkpolicy.yaml      # optional default-deny egress skeleton
  README.md
```

**values.yaml** must support (landing-aligned):

```yaml
global:
  namespace: kubemind-system
  airGapped: false
  imageRegistry: ""

router:
  replicaCount: 2
  port: 9080
  semanticCache:
    enabled: true
mind:
  replicaCount: 2
  port: 9081
agents:
  replicaCount: 1
  port: 9082
sentinel:
  replicaCount: 1
  port: 9083
```

**Acceptance:** `helm lint charts/kubemind` passes.

#### T5.2 — Image build tags

Update `Makefile`:

- `make build` tags `kubemind/router:dev` etc.  
- Document `kind load docker-image` flow  

**Acceptance:** kind install runbook in `charts/kubemind/README.md`.

#### T5.3 — Retire legacy manifests

- Move `k8s/*.yaml` → `k8s/legacy/` **or** delete after chart parity  
- Update any docs referencing switchboard/contextweave/deepagents/tracer  

**Acceptance:** No active docs tell users to apply legacy names.

#### T5.4 — HPA & health probes

- HPA on router (CPU/memory)  
- Readiness/liveness: `GET /health` on all services  
- Resource requests/limits sane defaults  

**Acceptance:** Probes configured; HPA manifest present.

#### T5.5 — Install verification script

**File:** `scripts/verify-helm-install.sh`

Checks:

1. All pods Running  
2. curl each `/health` via port-forward or ingress  
3. Exit non-zero on failure  

**Makefile:** `make helm-verify`

**Acceptance:** Scripted smoke on kind.

### Phase 5 exit criteria

- [ ] Chart installs cleanly  
- [ ] Four services healthy  
- [ ] Legacy names retired from primary path  
- [ ] README deploy section uses Helm  

---

## 10. Phase 6 — SDKs

**Duration:** 1.5 weeks  
**Path:** `sdk/`  
**Depends on:** Phase 1 (`/v1/route` stable)  

### Goals

Multi-language clients matching Code Hub intent.

### Tasks (detailed)

#### T6.1 — Python SDK

```text
sdk/python/
  pyproject.toml
  src/kubemind/
    __init__.py
    router.py      # RouterClient.route()
    mind.py
    agents.py
    sentinel.py
    types.py
  examples/route_prompt.py
  tests/
```

`RouterClient`:

- `endpoint`, `api_key`/`workspace_id`, `enable_semantic_cache`, `cache_threshold`  
- `route(prompt, preferred_target=..., fallback=...)`  
- Raises typed errors on 4xx/5xx  

**Acceptance:** Example runs against compose; unit tests with httpx mock.

#### T6.2 — Go SDK

```text
sdk/go/
  go.mod   # module github.com/kubemind/sdk-go
  router/client.go
  examples/route/main.go
```

Share types with CLI where practical (`cmd` may import sdk later).

**Acceptance:** `go test ./...` green; example builds.

#### T6.3 — TypeScript SDK

```text
sdk/typescript/
  package.json
  src/index.ts
  src/router.ts
  examples/route.ts
```

**Acceptance:** `npm test` or tsc build; example runs under tsx/node.

#### T6.4 — Versioning & docs

- Semver `0.1.0`  
- `sdk/README.md` install instructions (path/git for now; publish later)  
- Update landing Code Hub only after packages exist (separate landing PR)

**Acceptance:** Root README links to `sdk/README.md`.

### Phase 6 exit criteria

- [ ] Three SDKs with working route example  
- [ ] Docs for local install  
- [ ] CI job optional later  

---

## 11. Phase 7 — Hard security (optional)

**Duration:** 2+ weeks  
**Depends on:** Phases 1–5  

### Tasks (high level)

1. NetworkPolicies default-deny egress + allow DNS/in-cluster  
2. Optional Envoy/Linkerd/Istio mTLS between services  
3. SPIFFE/SPIRE evaluation spike doc  
4. Cosign image signing in CI  
5. SOC2 evidence checklist (process), not code-only  

### Exit criteria

- [ ] Design doc + at least NetworkPolicies in chart  
- [ ] mTLS spike documented even if not default-on  

---

## 12. Master checklist (copy into issues)

```text
Phase 0 — Identity
[x] T0.1 ADR KubeMind naming
[x] T0.2 docs/api.md inventory
[x] T0.3 shared/schemas README + skeletons
[x] T0.4 legacy k8s map
[x] T0.5 README KubeMind branding

Phase 1 — Router
[x] T1.1 semantic cache design note
[x] T1.2 SemanticCache implementation
[x] T1.3 response metadata
[x] T1.4 intent classifier
[x] T1.5 vLLM / DeepSeek / Anthropic providers
[x] T1.6 POST /v1/route
[x] T1.7 tests + sentinel attributes + log rename

Phase 2 — Mind
[x] T2.1 pgvector first-class + HNSW
[x] T2.2 chunking config
[x] T2.3 POST /v1/memory/query
[x] T2.4 tenant isolation tests
[x] T2.5 backends interface stubs

Phase 3 — Sentinel
[x] T3.1 PII redaction
[x] T3.2 injection heuristics
[x] T3.3 Prometheus /metrics
[x] T3.4 OTLP optional
[x] T3.5 GET /v1/telemetry/traces
[x] T3.6 export enrichment

Phase 4 — Agents
[ ] T4.1 k8s tools
[ ] T4.2 HITL approve/reject
[ ] T4.3 simple DAG
[ ] T4.4 POST /v1/task/dispatch
[ ] T4.5 k8s-scope honesty doc

Phase 5 — Helm
[ ] T5.1 chart scaffold
[ ] T5.2 image tags Makefile
[ ] T5.3 retire legacy k8s
[ ] T5.4 HPA + probes
[ ] T5.5 verify script

Phase 6 — SDKs
[ ] T6.1 Python
[ ] T6.2 Go
[ ] T6.3 TypeScript
[ ] T6.4 versioning docs

Phase 7 — Hard security (optional)
[ ] NetworkPolicies
[ ] mTLS spike
[ ] Signing / SOC2 process notes
```

---

## 13. Suggested issue labels

- `phase/0-identity` … `phase/7-security`  
- `service/router|mind|agents|sentinel|helm|sdk`  
- `priority/p0|p1|p2`  
- `type/feature|docs|tech-debt`

---

## 14. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Scope explosion (Rust, Temporal, ClickHouse) | MVP substitutes; honesty docs; landing tech label updates |
| Semantic cache latency budget | Embed async warm-up; short-circuit exact hash first; tune threshold |
| pgvector image surprise | Switch compose to `pgvector/pgvector:pg16` early in Phase 2 |
| K8s tool safety | Default read-only SA; HITL for mutations |
| Dual CLI names | Alias period; ADR timeline for dropping `tricore` |

---

## 15. Success metrics

| Metric | Target |
|--------|--------|
| Core services exist | 4/4 (done) |
| Landing API aliases | `/v1/route`, `/v1/memory/query`, `/v1/task/dispatch`, `/v1/telemetry/traces` |
| Semantic cache | Demonstrable hit with metadata |
| Helm smoke | All `/health` OK on kind |
| SDKs | ≥1 language fully; goal 3 |
| Security basics | Redaction + Prometheus |

---

## 16. Immediate next actions

1. Merge this file as the living plan under `docs/KUBEMIND_IMPLEMENTATION_PLAN.md` (**done when committed**).  
2. Execute **Phase 0** (ADR + API inventory + README branding).  
3. Start **Phase 1** (semantic cache + `/v1/route`) — highest credibility unlock for the landing story.

---

## 17. Related paths

| Path | Notes |
|------|-------|
| `services/*` | Control plane implementation |
| `docker-compose.yml` | Local dev stack |
| `k8s/` | Legacy manifests → replace via chart |
| `charts/kubemind/` | **To create** (Phase 5) |
| `sdk/` | **To create** (Phase 6) |
| `cmd/tricore` | CLI; rename/alias in Phase 0/6 |
| `landing_7/` | Marketing only — update claims as exit criteria met |
| `docs/api.md` | **To create** (Phase 0) |
| `docs/adr/` | **To create** (Phase 0) |
