# ADR 0001: KubeMind product naming

**Status:** Accepted  
**Date:** 2026-07-26  
**Decision makers:** Platform  

## Context

The repository directory and several artifacts still use the name **Tricore** (CLI binary, Docker Compose comments, K8s namespace `tricore`, legacy manifests named `switchboard` / `contextweave` / `deepagents` / `tracer`). Marketing and the primary landing experience brand the product as **KubeMind**. Dual identity confuses docs, image tags, Helm, and SDKs.

## Decision

The canonical product name is **KubeMind**. All new work uses KubeMind identifiers. Tricore remains a transitional alias only where required for backwards compatibility during one release cycle.

| Concept | Canonical value |
|---------|-----------------|
| Product name | KubeMind |
| K8s namespace | `kubemind-system` |
| Helm chart / release | `charts/kubemind`, release name `kubemind` |
| Container images | `kubemind/router`, `kubemind/mind`, `kubemind/agents`, `kubemind/sentinel`, `kubemind/dashboard` |
| In-cluster DNS | `router.kubemind-system.svc.cluster.local`, etc. |
| Host ports (dev) | `9080` router · `9081` mind · `9082` agents · `9083` sentinel · `9000` dashboard |
| Internal container ports | `8080` · `8081` · `8082` · `8083` · `3000` (dashboard) |
| CLI (canonical) | **`kmind`** |
| CLI binary path | `bin/kmind` |
| CLI config dir | `~/.kmind/` (`~/.tricore/` still read as fallback) |
| CLI (transition) | `tricore` may be a symlink to `kmind` for one release |
| Env var prefix (prefer) | `KUBEMIND_*` |
| Env var prefix (accept) | Existing unprefixed and legacy vars for one release (e.g. `DATABASE_URL`, `REDIS_URL`, `ROUTER_URL`) |
| Workspace header | `X-Workspace-ID` (unchanged) |
| Repo directory name | May remain `tricore` on disk; product is still KubeMind |

### Service names (never use legacy in new code)

| Service | Port | Role |
|---------|------|------|
| `router` | 9080 | LLM gateway, cache, routing |
| `mind` | 9081 | Knowledge graph + hybrid search |
| `agents` | 9082 | Mission / agent execution |
| `sentinel` | 9083 | Traces, metrics, streaming |

### Legacy names (do not use in new manifests or docs)

| Legacy | Replace with |
|--------|----------------|
| Tricore (product) | KubeMind |
| namespace `tricore` | `kubemind-system` |
| `switchboard` | `router` |
| `contextweave` | `mind` |
| `deepagents` | `agents` |
| `tracer` / `beacon_trace` package dual | `sentinel` |
| Log prefix `SwitchBoard` | `router` or `KubeMind` |
| Image `pisigmac/tricore-*` | `kubemind/*` |

See also: [Legacy K8s migration map](../migration/legacy-k8s.md).

## Consequences

### Positive

- Single brand for landing, Helm, SDKs, and ops docs  
- Clear mapping for Phase 5 chart work and Phase 6 packages (`kubemind` Python/Go/TS)  

### Negative / follow-up

- Existing clones and scripts may still say `tricore`  
- CLI rename requires Makefile and docs updates (Phase 0 partial; complete with SDK/CLI work)  
- Docker Compose service keys can stay `router`/`mind`/… (already correct); only product framing changes now  

### Non-goals of this ADR

- Full mechanical rename of every Python package path (`router` module names already match)  
- Publishing packages to PyPI/npm  
- Implementing semantic cache / Helm (later phases)  

## Compliance

New PRs that introduce `switchboard`, `contextweave`, `deepagents`, or namespace `tricore` should be rejected unless they are migration shims explicitly marked deprecated.
