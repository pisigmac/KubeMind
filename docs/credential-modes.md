# Credential modes

KubeMind supports two mutually exclusive deployment modes. The mode is chosen
at process startup, applies to the whole router, and cannot be overridden by a
request, Workspace, profile, or model.

| Mode | Intended use | Provider access |
|---|---|---|
| `keymint` | Production and Zetakube integration | Connection reference → one-use KeyMint capability → KeyMint proxy |
| `direct` | Explicit self-hosted development or migration compatibility | Deployment secret → KubeMind provider client |

Configure `credential_mode` in `services/router/config/gateway.yaml` or set
`KUBEMIND_CREDENTIAL_MODE` at process startup. The environment value is a
deployment override. Missing and unknown values fail startup.

## KeyMint mode

- This is the production default in the committed gateway and Helm values.
- Every configured provider, including Ollama and vLLM, is catalog metadata;
  KubeMind does not construct a provider client or retain a provider key.
- The Zetakube Runtime path resolves one trusted Connection reference, binds
  tenant/Workspace/Project/Run/model/operation/expiry/one-use/cost scope, and
  sends only the resulting capability through KeyMint's provider proxy.
- Expired, revoked, mismatched, malformed, or unavailable capabilities fail
  closed with stable error codes.
- KeyMint failure never activates direct mode.
- The legacy direct chat and embedding endpoints cannot execute catalog-only
  providers. A Connection-aware product/API surface must invoke the Runtime
  adapter; until that composition is deployed, these endpoints return no
  eligible provider rather than bypassing KeyMint.

## Direct mode

- Compose defaults to this mode for the current laptop quickstart.
- Provider credentials must come from deployment secrets/environment, never
  committed YAML, API payloads, traces, caches, or public definitions.
- Local and cloud provider clients execute inside KubeMind.
- `/health` reports `credential_mode: direct` and a security warning.
- Direct mode is not accepted by the Zetakube Runtime adapter.

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
