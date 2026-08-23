# KubeMind product

Status: `dev` branch — not production-certified, not sold yet  
Audience: operators and implementers

KubeMind is sold as a **self-hosted AI gateway**, not as Zetakube and not as
an autonomous-agent platform. This file is the SKU. Marketing pages must not
outrank it.

## What we sell (v1)

| SKU | Components | Customer job |
|---|---|---|
| **KubeMind Gateway** | Router, Sentinel, Dashboard | Classify intent, enforce sensitivity policy, route to an allowed model, record a decision |
| **KubeMind Knowledge** (add-on) | Mind | Tenant-isolated retrieval that the router may attach |
| **Not sold** | Agents | Preview only. Shell/filesystem tools are not a production sandbox |

Credentials in production go through **KeyMint**. KubeMind must not hold
long-lived provider keys in a paid deployment.

## Production deployment contract

Set `KUBEMIND_DEPLOYMENT=production`. The process then **refuses to start** if:

- API keys are missing (open mode that trusts `X-Workspace-ID`)
- `credential_mode` / `KUBEMIND_CREDENTIAL_MODE` is `direct`

Local Compose remains `KUBEMIND_DEPLOYMENT=local` so a laptop can run Ollama
in direct mode. That stack is a developer preview. It is not the product you
invoice.

Helm defaults: `credentialMode: keymint`, `auth.required: true`, Agents
replicas `0`.

## Claims that are allowed

- Intent classification plus a **policy engine that does not trust the classifier** for sensitivity
- Workspace derived from API key, not from a caller-controlled header
- KeyMint mode: metadata-only providers; capabilities redeemed at the proxy
- Deterministic policy reason codes on the Runtime path
- Local `make ci` as a quality gate, not as an SLA

## Claims that are forbidden until evidenced

- “World’s first”, cheapest, best model, residency, or uptime guarantees
- Production-grade agent missions or shell isolation
- Live-provider cost savings versus explicit routing
- Hosted SaaS multi-tenant KubeMind (this SKU is self-hosted)

## Release bar before a paying customer

1. Clean `dev` commit; `make ci` from a fresh clone
2. Helm install with KeyMint, two workspaces, cross-tenant denial
3. Revoke-during-use and KeyMint outage fail closed
4. Backup/restore of Postgres (and Redis if used for cache)
5. Agents remain off unless the customer signs a preview waiver
6. Dependency-license review and a digest-pinned image
7. Named on-call and a rollback that disables admission

Until that list is green, the honest status is **developer preview on `dev`**.
