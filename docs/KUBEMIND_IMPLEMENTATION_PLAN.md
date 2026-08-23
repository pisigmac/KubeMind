# KubeMind Implementation Plan

**Canonical product name:** KubeMind (formerly dual-branded as Tricore)  
**Repo path:** `/home/oh20210736-ud/Documents/WorkSpace/kubemind`  
**Landing reference:** `landing_8` (intent-aware gateway; prior iterations under other `landing_*` dirs)  
**Status:** Living plan — Phases 0–3 + intent/governance wedge **shipped**; Phase 5 Helm **partial**; Phases 4 / 6 / 7 open  
**Last updated:** 2026-08-04  

**Companion docs:** [`architecture.md`](./architecture.md) · [`design/intent-routing.md`](./design/intent-routing.md) · [`api.md`](./api.md)

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
| K8s namespace (shipped) | **`kubemind`** (chart + compose story). ADR 0001 still lists `kubemind-system` — amend ADR to match chart. |
| Helm release / chart | `kubemind` / `charts/kubemind` (chart version `0.3.0`) |
| Image registry prefix | `kubemind/` (or org-owned equivalent) |
| CLI (canonical) | **`kmind`** (`bin/kmind`; `bin/tricore` symlink for one release) |
| Public host ports | `9080` router · `9081` mind · `9082` agents · `9083` sentinel · `9000` dashboard |
| Auth | `X-API-Key` → workspace (`shared/python/kubemind_auth`); open mode trusts `X-Workspace-ID` for local dev only |

Legacy names to retire from **primary** docs/paths: `tricore` namespace, `switchboard`, `contextweave`, `deepagents`, `tracer`, `SwitchBoard` log prefixes. Raw files under `k8s/` remain until Phase 5 cleanup finishes.

---

## 2. Current inventory (codebase fact) — 2026-08-04

### 2.1 Services that exist

| Service | Port | Path | Language | Role today |
|---------|------|------|----------|------------|
| **router** | 9080 | `services/router` | Python FastAPI | Intent + policy gateway, exact/semantic cache, profiles, cascade, metrics |
| **mind** | 9081 | `services/mind` | Python FastAPI | Knowledge ingest, hybrid search (vector+keyword+graph), pgvector |
| **agents** | 9082 | `services/agents` | Python FastAPI | Mission planner + tools (fs/shell/web/knowledge); **not** K8s-native yet |
| **sentinel** | 9083 | `services/sentinel` | Python FastAPI | Spans, redaction/guardrails, Prometheus, audit ledger, WebSocket stream |
| **dashboard** | 9000 | `dashboard/` | Next.js | Operator UI (not end-user chat) |
| **CLI** | — | `cmd/tricore` → `bin/kmind` | Go | Stack/ops control |
| **Shared libs** | — | `shared/python/kubemind_auth`, `kubemind_policy` | Python | API-key tenancy; redaction + injection detectors |
| **Schemas** | — | `shared/schemas/` | JSON Schema | Portable contracts for SDKs/docs |
| **Helm** | — | `charts/kubemind/` | Helm | Control-plane chart (partial vs full Phase 5 exit) |
| **Marketing** | — | `landing_8/` | Next.js 15 | Partner landing (not in compose) |

Compose stack (`docker-compose.yml`): Postgres+pgvector `:9432`, Redis `:9379`, Ollama `:9434`, four services + dashboard.

### 2.2 What already works (do not rebuild)

**Router**
- `POST /v1/chat/completions`, `POST /v1/route`, `POST /v1/embeddings`, `POST /v1/classify`
- Exact Redis cache + semantic cache (Redis list or pgvector); model-aware / intent-partitioned keys
- Intent: rules prior + k-NN (+ optional linear head), margin confidence, abstain, `_background` decoy
- Route profiles + sensitivity policy overlay (`allow` / `redact` / `local_only` / `block`)
- Mind retrieval for retrieval intents; cascade escalation; decision records → sentinel
- Providers: Ollama, vLLM, DeepSeek-local, OpenAI-compat, Anthropic (env-gated)
- `/metrics`, `/v1/routing/report`, feedback path; eval under `services/router/eval/`

**Mind**
- `POST /v1/ingest`, `POST /v1/query`, `POST /v1/memory/query`, `GET /v1/graph`
- pgvector HNSW in default compose; workspace scoping; connectors (doc/git/web)

**Agents**
- `POST /v1/missions`, tools invoke, planner loop calling router/mind/sentinel

**Sentinel**
- Spans, redaction, injection heuristics, `/metrics`, OTLP optional, `/v1/telemetry/traces`
- Hash-chained audit ledger (`/v1/audit/verify`, head, entries, retention)
- `WS /v1/stream`

**Platform**
- Local-first Ollama path; `make up` / `make demo` (`scripts/partner_demo.sh`)
- Unit/eval coverage on router + sentinel; `bin/kmind` builds from `cmd/tricore`
- Docs: `docs/architecture.md`, `docs/design/intent-routing.md`, `docs/api.md`

### 2.3 Remaining gaps vs landing / MVP

| Claim / goal | Code reality | Severity |
|--------------|--------------|----------|
| K8s autonomous agents / OPA / Temporal | Generic tools only; no cluster client / HITL | **P1** |
| `POST /v1/task/dispatch` | Missing alias | P1 |
| Helm “install and healthy on kind” | Chart scaffold + deployments exist; no `verify-helm-install.sh`; legacy `k8s/` still present | P1 |
| Python/Go/TS SDKs | Missing (`sdk/` not created) | P1 |
| CLI ↔ dashboard shared clients | Thin ad-hoc HTTP; Phase 6 SDKs intended | P1 |
| Dashboard API keys | Still often `X-Workspace-ID: default` | P1 |
| mTLS / SPIFFE / Envoy | Missing | P2 |
| ClickHouse / eBPF / Rust rewrite | Non-goal MVP | P2 |
| ADR namespace vs chart | ADR says `kubemind-system`; shipped chart uses `kubemind` | Docs hygiene |

**Shipped (no longer gaps):** semantic cache, `/v1/route`, intent classification, vLLM/DeepSeek configs, pgvector mind path, `/v1/memory/query`, PII/injection controls, Prometheus on router+sentinel, Helm chart present, product naming largely KubeMind.

---

## 3. Strategy

**Track A — Capability (this plan):** Finish remaining phases under KubeMind naming.

**Track B — Truth (ongoing):** Do not advertise Rust/gRPC/Temporal/ClickHouse/eBPF until real. Prefer landing tech labels: Python, FastAPI, Postgres, Redis, Ollama/vLLM, Helm. Landing (`landing_8`) must stay honest to §2.

**MVP definition of “landing-credible”:**

1. [x] Semantic cache path works end-to-end  
2. [x] Core landing API aliases (`/v1/route`, `/v1/memory/query`, `/v1/telemetry/traces`)  
3. [~] `helm install kubemind` brings up healthy control plane — chart exists; kind verify script + legacy retire still open  
4. [ ] At least one SDK (`python`) works against local stack  
5. [x] Basic PII redaction + Prometheus metrics  
6. [ ] Agents can read Kubernetes resources (list/logs)  
7. [x] Intent-aware routing + enforced governance (see §5b)

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
- Namespace `kubemind` (shipped; ADR originally said `kubemind-system` — amend)
- Service DNS: `router.kubemind.svc`, etc.
- Env var prefix migration: prefer `KUBEMIND_*`, accept `TRICORE_*` / legacy for one release
- Image names: `kubemind/router`, `kubemind/mind`, `kubemind/agents`, `kubemind/sentinel`, `kubemind/dashboard`
- CLI: **`kmind`** entrypoint; `tricore` may remain a symlink for 1 release

**Acceptance:** ADR merged; README title section references KubeMind.

#### T0.2 — API inventory from live FastAPI apps

**File:** `docs/api.md`

For each service, document:

| Method | Path | Purpose | Request body summary | Auth header |
|--------|------|---------|----------------------|-------------|
| … | … | … | … | `X-API-Key` (preferred) or `X-Workspace-ID` in open mode |

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
| namespace `tricore` | `kubemind` |

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

#### T1.4 — Intent classification (lightweight) — **superseded by §5b**

**File:** `services/router/src/router/intent.py`

Original MVP options (keyword/centroid or small classify prompt) were completed as a first cut, then replaced by the shipped intent + governance wedge (§5b): rules prior + k-NN over examples, margin confidence, route profiles, and a sensitivity policy overlay that must not depend on the classifier.

Historical acceptance (still true): intent appears in response metadata; routing targets influence provider selection when healthy.

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

## 5b. Phase 1b — Intent-aware gateway & governance (shipped)

**Status:** Done (2026-08)  
**Paths:** `services/router`, `services/sentinel`, `shared/python/`, `docs/design/intent-routing.md`  
**Depends on:** Phase 1 semantic cache + `/v1/route`

### Design invariant

**A governance decision must never depend on the intent classifier.**  
`router.policy` does not import `router.intent`. Detectors live in `shared/python/kubemind_policy` (router inline + sentinel at ingest).

### What shipped

| Area | Location / behavior |
|------|---------------------|
| API-key tenancy | `shared/python/kubemind_auth` — workspace from `X-API-Key`; service key for in-cluster |
| Intent classifier | Rules prior + k-NN examples; margin confidence; abstain → `general`; `_background` decoy |
| Route profiles | `gateway.yaml` profiles (pool, model, params, cache, retrieval) |
| Policy overlay | `allow` / `redact` / `local_only` / `block`; `local_only` never falls back to cloud |
| Embed once | Exact cache first; single embed shared by intent + semantic cache |
| Cache | Model-aware match keys; intent stored on entries; intent partitioning when confident |
| Mind retrieval | Router client for retrieval intents |
| Decision record | Per-request record → sentinel ledger + routing metrics |
| Audit ledger | Hash-chained; `/v1/audit/verify`, head, entries, retention/legal hold |
| Cascade | Optional cheap-local-first escalation |
| Eval | `services/router/eval/` — labeled set, consequence-weighted harness, threshold sweep, linear-head gate |
| Demo | `make demo` / `scripts/partner_demo.sh` |
| Docs | `docs/architecture.md`, `docs/design/intent-routing.md`, `docs/api.md` updates |

### Exit criteria

- [x] Classifier + profiles + policy overlay on chat/route path  
- [x] Shared policy package used by router and sentinel  
- [x] Workspace bound to API keys across router/mind/agents/sentinel  
- [x] Audit ledger verify path  
- [x] Eval harness + operating point documented  
- [x] Partner demo script  

**Do not rebuild** this wedge; extend via `gateway.yaml` intents/profiles and eval dataset growth.

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

**Acceptance:** Integration test against kind/minikube or mocked client; mission can list pods in `kubemind`.

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
  "namespace": "kubemind"
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
**Status:** **Partial** — chart `0.3.0` installs the four services + dashboard + Postgres/Redis; remaining exit items below  

### Goals

Make `helm upgrade --install kubemind ./charts/kubemind -n kubemind --create-namespace` the primary deploy path (shipped namespace: **`kubemind`**).

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

**values.yaml** (shipped shape — see `charts/kubemind/values.yaml`):

```yaml
namespace: kubemind
image:
  router: kubemind/router:0.3.0
  # mind, agents, sentinel, dashboard…
replicas:
  router: 2
  mind: 1
  agents: 1
  sentinel: 1
  dashboard: 1
# auth.apiKeys / serviceKey / adminKey, semanticCacheBackend, postgres, redis…
```

**Acceptance:** `helm lint charts/kubemind` / `make helm-template` passes. **Done** for scaffold + combined Deployment/Service template.

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

### Phase 5 progress

| Task | Status |
|------|--------|
| T5.1 Chart scaffolding + deployments/services/config/secrets/ingress | **Done** (`charts/kubemind/`) |
| T5.2 Image tags via `make build` → `kubemind/*` | **Done** |
| T5.3 Retire legacy `k8s/` manifests from primary path | **Open** (files still at `k8s/*.yaml`) |
| T5.4 HPA on router | **Open** (probes exist on deployments) |
| T5.5 `scripts/verify-helm-install.sh` + `make helm-verify` | **Open** (`make helm-template` only) |

### Phase 5 exit criteria

- [x] Chart scaffolds and templates cleanly (`make helm-template`)  
- [~] Four services healthy on kind — needs verify script / runbook proof  
- [ ] Legacy names retired from primary path (`k8s/` → `k8s/legacy/` or delete)  
- [x] Chart README documents Helm install  
- [ ] Amend ADR 0001 namespace to `kubemind` (or document alias)  

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
[x] T1.4 intent classifier (superseded/extended by Phase 1b)
[x] T1.5 vLLM / DeepSeek / Anthropic providers
[x] T1.6 POST /v1/route
[x] T1.7 tests + sentinel attributes + log rename

Phase 1b — Intent + governance
[x] API-key workspace binding (kubemind_auth)
[x] Shared kubemind_policy (redact + guardrails)
[x] k-NN intent + profiles + policy overlay
[x] Embed-once + model/intent-aware cache
[x] Decision records + audit ledger
[x] Eval harness + partner demo
[x] architecture + intent-routing docs

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
[x] T5.1 chart scaffold + deployments
[x] T5.2 image tags Makefile
[ ] T5.3 retire legacy k8s
[ ~] T5.4 probes done; HPA open
[ ] T5.5 verify script
[ ] Amend ADR namespace → kubemind

Phase 6 — SDKs
[ ] T6.1 Python
[ ] T6.2 Go (CLI imports sdk)
[ ] T6.3 TypeScript (dashboard uses sdk)
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

| Metric | Target | Status |
|--------|--------|--------|
| Core services exist | 4/4 | Done |
| Landing API aliases | `/v1/route`, `/v1/memory/query`, `/v1/telemetry/traces`, `/v1/task/dispatch` | 3/4 (`task/dispatch` open) |
| Semantic cache | Demonstrable hit with metadata | Done |
| Intent + governance | Classify + policy + ledger | Done |
| Helm smoke | All `/health` OK on kind | Partial (chart yes; verify script no) |
| SDKs | ≥1 language fully; goal 3 | Open |
| Security basics | Redaction + Prometheus | Done |
| K8s agent tools | List/logs + HITL mutations | Open |

---

## 16. Immediate next actions

1. **Phase 5 finish:** move/retire `k8s/` legacy manifests; add HPA; add `scripts/verify-helm-install.sh` + `make helm-verify`; amend ADR namespace to `kubemind`.  
2. **Phase 4:** Kubernetes read tools + HITL for mutations + `/v1/task/dispatch` + honesty doc (`docs/agents/k8s-scope.md`).  
3. **Phase 6:** Python SDK first (`RouterClient.route`); then Go (CLI) and TypeScript (dashboard).  
4. Keep **`landing_8`** claims tied to §2.3 — do not advertise Temporal/OPA/mTLS/SDKs until shipped.  
5. Optional: Phase 7 NetworkPolicies once Helm verify is green.

---

## 17. Related paths

| Path | Notes |
|------|-------|
| `services/*` | Control plane implementation |
| `shared/python/kubemind_auth`, `kubemind_policy` | Shared auth + detectors |
| `shared/schemas/` | Portable JSON Schema contracts |
| `docker-compose.yml` | Local dev stack |
| `k8s/` | Legacy manifests — retire in Phase 5 |
| `charts/kubemind/` | **Exists** (v0.3.0); finish verify + HPA + legacy retire |
| `sdk/` | **To create** (Phase 6) |
| `cmd/tricore` → `bin/kmind` | CLI; Go SDK import in Phase 6 |
| `dashboard/` | Operator UI; TS SDK in Phase 6 |
| `landing_8/` | Marketing — intent-aware gateway story |
| `scripts/partner_demo.sh` | Partner demo (`make demo`) |
| `docs/api.md` | Live API inventory |
| `docs/architecture.md` | System map + pipeline |
| `docs/design/intent-routing.md` | Classifier / policy / eval |
| `docs/adr/0001-kubemind-naming.md` | Naming ADR (namespace amend pending) |
