# Credential modes

**Current as of: Release v0.3.3**

KubeMind supports two mutually exclusive deployment modes. The mode is chosen
at process startup, applies to the whole router, and cannot be overridden by a
request, Workspace, profile, or model.

| Mode | Intended use | Provider access |
|---|---|---|
| `keymint` | Production zero-trust mode | Connection reference → one-use KeyMint capability → KeyMint proxy |
| `direct`  | Explicit self-hosted/migration mode | Deployment-secret provider keys configured directly |

Configure `credential_mode` in `services/router/config/gateway.yaml` or set
`KUBEMIND_CREDENTIAL_MODE` at process startup. The environment value is a
deployment override. Missing and unknown values fail startup.

## KeyMint mode

- Router provider definitions hold metadata only (model catalog, cost, rate limits, policy constraints).
- Secret provider credentials (OpenAI/Anthropic/custom keys) remain inside KeyMint.
- The router resolves one trusted Connection reference, binds
  an explicit scope (`workspace_id`, `project_id`, `run_id`, `model`, `operation`,
  `audience`, `expires_at`, `max_cost_micros`), issues a single-use capability, and
  sends only the resulting capability through KeyMint's provider proxy.
- KeyMint issues short-lived, HMAC-SHA256-signed capability tokens with audience `keymint-provider-proxy`.
- KeyMint failure never activates direct mode.
- KeyMint revocation, expiry, budget denial, or proxy unreachable returns a safe error code (e.g. `CAPABILITY_DENIED`, `CAPABILITY_EXPIRED`, `CAPABILITY_UNAVAILABLE`).
- If one KeyMint Connection fails, deterministic routing considers the next
  eligible provider rather than bypassing KeyMint.

## Direct mode

- Direct mode is an explicit self-hosted compatibility mode.
- Direct mode accepts provider API keys via environment variables/Kubernetes secrets for local development.
- Provider credentials must come from deployment secrets/environment, never
  committed YAML, API payloads, traces, caches, or public definitions.
- Local and cloud provider clients execute inside KubeMind.
- `/health` reports `credential_mode: direct` and a security warning.

## Switching modes

Switching requires a controlled deployment restart. Do not configure both
credential architectures as a fallback chain. Before moving to KeyMint:

1. Create and validate KeyMint Connections for every provider target.
2. Remove provider-key injection from the KubeMind deployment.
3. Set `KUBEMIND_CREDENTIAL_MODE=keymint`.
4. Restart and verify `/health` reports `keymint`.
5. Exercise expiry, revocation, KeyMint outage, model scope, budget scope, and
   cross-Workspace denial with synthetic credentials.

Rollback to direct mode is an explicit operator decision and requires a new
deployment with separately provisioned secrets. It is never automatic.
