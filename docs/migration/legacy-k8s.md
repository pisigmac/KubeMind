# Legacy Kubernetes manifests → KubeMind

**Status:** Phase 0 map (implementation in Phase 5 Helm)  
**Product:** KubeMind  
**Target namespace:** `kubemind-system`

## Why this exists

The `k8s/` directory still describes an older Tricore deployment with service names that **do not match** `docker-compose.yml` or `services/*`:

| Legacy file | Legacy app name | KubeMind service | Host port | Container port |
|-------------|-----------------|------------------|-----------|----------------|
| `k8s/switchboard.yaml` | `switchboard` | **router** | 9080 | 8080 |
| `k8s/contextweave.yaml` | `contextweave` | **mind** | 9081 | 8081 |
| `k8s/deepagents.yaml` | `deepagents` | **agents** | 9082 | 8082 |
| `k8s/tracer.yaml` | `tracer` | **sentinel** | 9083 | 8083 |
| `k8s/dashboard.yaml` | dashboard | **dashboard** | 9000 | 3000 |
| `k8s/postgres.yaml` | postgres | **postgres** | 9432 (dev) | 5432 |
| `k8s/redis.yaml` | redis | **redis** | 9379 (dev) | 6379 |
| `k8s/namespace.yaml` | `tricore` | **`kubemind-system`** | — | — |
| `k8s/configmap.yaml` | tricore-config | kubemind-config | — | — |
| `k8s/secrets.yaml` | tricore-secrets | kubemind-secrets | — | — |

## Do not

- Point new runbooks at `kubectl apply -f k8s/switchboard.yaml` as the primary install path  
- Use images like `pisigmac/tricore-switchboard` in new charts  
- Create new resources in namespace `tricore`

## Do

- Build Helm chart under `charts/kubemind/` (Phase 5) with Deployments named `router`, `mind`, `agents`, `sentinel`  
- After chart parity: move current `k8s/*.yaml` to `k8s/legacy/` **or** delete and keep only a pointer README  
- Align HPA to **router** (legacy HPA is on `switchboard`)

## Image rename matrix

| Legacy image (example) | Target |
|------------------------|--------|
| `pisigmac/tricore-switchboard` | `kubemind/router` |
| `pisigmac/tricore-contextweave` | `kubemind/mind` |
| `pisigmac/tricore-deepagents` | `kubemind/agents` |
| `pisigmac/tricore-tracer` | `kubemind/sentinel` |
| dashboard image (if any) | `kubemind/dashboard` |

## DNS migration

| Legacy | KubeMind |
|--------|----------|
| `switchboard.tricore.svc` | `router.kubemind-system.svc` |
| `contextweave.tricore.svc` | `mind.kubemind-system.svc` |
| `deepagents.tricore.svc` | `agents.kubemind-system.svc` |
| `tracer.tricore.svc` | `sentinel.kubemind-system.svc` |

## Env vars used by services today

These remain valid; prefer documenting them under KubeMind ops docs:

- `DATABASE_URL`
- `REDIS_URL`
- `OLLAMA_BASE_URL`
- `ROUTER_URL`, `MIND_URL`, `SENTINEL_URL`
- `KUBEMIND_CREDENTIAL_MODE=keymint` for production. Provider credentials live
  in KeyMint Connections and must not be injected into KubeMind.
- `KUBEMIND_CREDENTIAL_MODE=direct` is an explicit self-hosted/development
  compatibility mode. It requires deployment-secret provider keys, is reported
  by `/health`, and is never an automatic fallback.

Optional later: `KUBEMIND_ROUTER_URL` as alias.

## Checklist for Phase 5

- [ ] `charts/kubemind` installs into `kubemind-system`
- [ ] No template references switchboard/contextweave/deepagents/tracer
- [ ] Probes hit `/health` on each service
- [ ] HPA targets router Deployment
- [ ] `scripts/verify-helm-install.sh` passes on kind
- [ ] This file updated with “legacy retired on &lt;date&gt;”
