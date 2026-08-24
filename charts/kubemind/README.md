# KubeMind Helm chart

Installs the four core services (`router`, `mind`, `agents`, `sentinel`), the
dashboard, Postgres with pgvector, and Redis — under the `kubemind` namespace.

Retired names from `k8s/` (`switchboard`, `contextweave`, `tricore`) are not
used here.

```bash
helm upgrade --install kubemind ./charts/kubemind \
  --namespace kubemind --create-namespace \
  --set auth.apiKeys='partner-key:acme' \
  --set auth.serviceKey='svc-shared' \
  --set auth.adminKey='admin' \
  --set auth.required=true
```

Semantic cache defaults to **pgvector**. Set `semanticCacheBackend=redis` for
the laptop-scale Redis list backend.

`credentialMode` defaults to `keymint`. In that mode KubeMind stores only
provider catalog metadata and calls must use scoped KeyMint
Capabilities (`--set credentialMode=direct` is available for offline / local testing).
The mode is fixed at process startup, appears in `/health`, and never falls
back automatically.

Prometheus scrapes `/metrics` on router and sentinel via the pod annotations.

### TraceLens Integration

Sentinel supports native telemetry span export to TraceLens (`/home/oh20210736-ud/Documents/WorkSpace/tracelens`):

```yaml
observability:
  tracelens:
    enabled: true
    endpoint: "http://tracelens-collector:8080"
    token: "your-tracelens-token"
```

When enabled, Sentinel formats all ingested spans into TraceLens `/v1/spans` batches and exports them asynchronously with Bearer token authentication.
