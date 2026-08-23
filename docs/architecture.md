# KubeMind architecture

**Product:** KubeMind — self-hosted, Kubernetes-native AI control plane  
**Status:** Living document (aligned with intent-routing + governance wedge)

## One-line claim

Every prompt is classified once — for **purpose** (intent) and for **sensitivity** (PII, secrets, injection) — and routed on both, with a tamper-evident record of the decision.

## System map

```
┌──────────────────────────────────────────────────────────────────┐
│  kmind CLI  ·  Dashboard :9000  ·  Partner landing (landing_8)   │
├──────────────────────────────────────────────────────────────────┤
│  router  :9080   Intent + policy gateway, cache, providers       │
│  mind    :9081   Knowledge graph, hybrid search, retrieval       │
│  agents  :9082   Missions, planning, tools                       │
│  sentinel:9083   Spans, audit ledger, metrics, live stream       │
├──────────────────────────────────────────────────────────────────┤
│  Postgres+pgvector  ·  Redis  ·  Ollama (local models/embeddings)│
└──────────────────────────────────────────────────────────────────┘
```

| Service | Role |
|---------|------|
| **router** | Only path for LLM calls. Classifies intent, enforces sensitivity, selects a route profile, optionally retrieves from mind, dispatches with fallback/cascade. |
| **mind** | Workspace knowledge. Queried by the router when intent is retrieval (`rag`). |
| **agents** | Long-running missions; all LLM traffic still goes through router. |
| **sentinel** | Observability plus the hash-chained audit ledger (`GET /v1/audit/verify`). |

## Credential ownership

KubeMind has one deployment-level `credential_mode`; requests cannot change
it. `keymint` is the production mode: router providers are metadata-only and
the Zetakube Runtime uses a Connection reference plus one-use KeyMint
capability. `direct` is an explicit self-hosted/migration mode in which
KubeMind receives deployment-secret provider keys. KeyMint failure never
falls back to direct mode. See [credential-modes.md](./credential-modes.md).

## Routing constraint precedence

Trusted tenant, operation, provider, data-region, budget and Connection scope
remove candidates before preferences are considered. Classifier abstention or
failure deterministically uses the general profile. Successful decisions emit
stable reason codes plus safe considered/eligible/selected provider names. See
[design/deterministic-routing.md](./design/deterministic-routing.md).

## Design invariant

**A governance decision must never depend on the intent classifier.**

Intent may abstain or be wrong — that costs quality or money. Sensitivity is a control — being wrong is a breach. `router.policy` does not import `router.intent`. Detectors live in `shared/python/kubemind_policy` so router (inline) and sentinel (at ingest) cannot drift apart.

## Request pipeline (router)

```
1. Auth                 workspace from API key (not a client-supplied header)
2. Exact cache          early return; no embedding on this path
3. Sensitivity          PII / secrets / injection on raw text
4. Embed once           shared by intent + semantic cache
5. Intent               k-NN (+ optional linear head) with margin confidence
6. Profile              pool, model, params, cache policy, retrieval flag
7. Policy overlay       redact / local_only / block over the profile pool
8. Semantic cache       model-aware signature; intent-partitioned when confident
9. Retrieval            mind augmentation for retrieval intents
10. Dispatch            direct provider client, or KeyMint capability proxy
11. Decision record     to sentinel ledger + routing metrics
```

Exact cache stays **in front of** embedding so the fastest path stays ~1ms. Intent is stored on cache entries because an exact hit never embeds and therefore cannot classify.

## Intent classification

- **Rules** — high-precision prior / hard overrides (`CrashLoopBackOff`, CVE ids).
- **k-NN** — over declarative examples in `gateway.yaml` (not centroids).
- **Confidence** — top-1 − top-2 margin; abstain to `general` below threshold.
- **Decoy class** — `_background` absorbs out-of-distribution prompts.
- **Calibration** — `make eval-calibrate` fits softmax temperature on a hold-out.
- **Linear head** — optional; `make eval-train-linear` ships only if it beats k-NN on consequence-weighted error.

Adding an intent is config: examples + a profile name. No code change.

## Sensitivity policy

Actions (most restrictive wins): `allow` < `redact` < `local_only` < `block`.

- Secrets / high injection → **block** before any provider sees the prompt.
- Personal data → **local_only**; if no healthy local provider exists → **503**, never cloud fallback.
- Sensitive prompts are not cached.

## Multi-tenancy

Workspace is derived from `X-API-Key` via `shared/python/kubemind_auth`, enforced in router, mind, agents, and sentinel. Open mode (trust `X-Workspace-ID`) is for local dev only. In-cluster service-to-service calls use `KUBEMIND_SERVICE_KEY`.

## Data plane

| Store | Use |
|-------|-----|
| Redis | Exact cache, rate limits, feedback queue, circuit-breaker state |
| Postgres + pgvector | mind vectors; optional semantic cache (`KUBEMIND_SEMANTIC_CACHE_BACKEND=pgvector`); audit ledger |
| SQLite | sentinel span table for single-node / tests (ledger prefers Postgres) |

## Deployment

- **Compose:** `make up` — local stack on ports 9080–9083, 9000.
- **Helm:** `charts/kubemind/` — namespace `kubemind`, images `kubemind/*`. Replaces retired `k8s/switchboard` / `tricore` names.
- **CLI:** `kmind` (`bin/kmind`).

## Observability & proof

- Router `/metrics` — intent distribution, policy actions, provider latency.
- Sentinel spans + WebSocket stream.
- Audit ledger — hash-chained per workspace; `GET /v1/audit/verify`.
- Routing report — `/v1/routing/report`; cache hits counted as **zero cost**.

## Further reading

| Doc | Topic |
|-----|--------|
| [design/intent-routing.md](./design/intent-routing.md) | Classifier, policy, eval methodology |
| [design/semantic-cache.md](./design/semantic-cache.md) | Cache design |
| [api.md](./api.md) | HTTP/WS inventory |
| [adr/0001-kubemind-naming.md](./adr/0001-kubemind-naming.md) | Naming |
| [../charts/kubemind/README.md](../charts/kubemind/README.md) | Helm install |
