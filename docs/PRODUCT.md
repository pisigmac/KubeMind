# KubeMind product

Status: `dev` — developer preview, not yet sold  
Branch: `dev` only. Do not ship `master`.

## Naming (do not blur this)

| Name | What it is |
|---|---|
| **KubeMind** | The product you sell |
| **Router** | Intelligent routing: classify, govern, choose a model, attach knowledge |
| **Mind** | The knowledge store the router queries (hybrid search, tenant-scoped) |
| **Sentinel** | Decision/audit log. Included, not a second SKU |
| **Agents** | Not the product. Preview. Off in Helm |

Customers buy **intelligent routing**. That is the Router. Mind is how routing
becomes knowledge-aware. Selling “Mind” as the router, or selling the router
without Mind, is the wrong product.

KubeMind is **not** Zetakube, not an agent platform, and not a GPU scheduler.

## What we sell (v1)

One SKU: **KubeMind** — self-hosted intelligent AI gateway.

```text
prompt
  → auth (workspace from API key)
  → sensitivity policy (never the classifier)
  → intent classification (may abstain)
  → profile (pool, model, retrieval?)
  → Mind retrieval when the profile says knowledge
  → dispatch to an eligible provider (KeyMint in production)
  → explainable routing_decision + Sentinel record
```

Included in the SKU: Router, Mind, Sentinel, Dashboard.  
Excluded: Agents.

Credentials in production: **KeyMint only**. Direct provider keys are a laptop
mode (`KUBEMIND_DEPLOYMENT=local`).

## Architecture that we are locking

1. **Router stays in front.** Mind has no public “pick a model” API. Knowledge
   is retrieved, then the router dispatches.
2. **Governance does not use the classifier.** Sensitivity/PII/injection can
   block or force `local_only` even if intent said `general`.
3. **Knowledge intents require Mind in production.** Empty results are allowed
   (nothing in the corpus). Mind down, timeout, or 5xx is `RETRIEVAL_UNAVAILABLE`
   and fails closed. Local Compose may continue without context and must label it.
4. **Silent degradation is not a feature.** A knowledge question answered as
   if retrieval succeeded, when it did not, is a product defect.
5. **Explain every route.** Responses include intent, profile, policy,
   selected provider, retrieval status, and a stable reason code. No prompts,
   keys, or provider URLs in that object.

## Production contract

`KUBEMIND_DEPLOYMENT=production` refuses to start if:

- API keys are missing (open mode / trusted `X-Workspace-ID`)
- credential mode is `direct`

Helm defaults: `deployment: production`, `credentialMode: keymint`,
`auth.required: true`, Mind replicas ≥ 1, Agents replicas `0`.

## Claims allowed vs forbidden

Allowed: intent-aware routing; policy independent of the classifier;
workspace from API key; KeyMint-held provider secrets; retrieval scoped by
workspace; explainable `routing_decision`; `make ci` as a quality gate.

Forbidden until evidenced: world’s first, cheapest, best model, residency,
uptime SLA, agent autonomy, live-provider savings vs explicit routing,
hosted multi-tenant SaaS.

## Remaining bar before a paying customer

1. `make ci` from a fresh clone of `dev`
2. Two-workspace Helm+KeyMint: cross-tenant knowledge denial
3. Knowledge prompt + Mind down → 503, not a fluent ungrounded answer
4. Knowledge prompt + empty corpus → answer labelled `retrieval_status=empty`
5. Revoke-during-use and KeyMint outage fail closed
6. Postgres backup/restore
7. Digest-pinned images and license review
8. On-call and a rollback that stops admission

Until that list is green, status is **developer preview**.
