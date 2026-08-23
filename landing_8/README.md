# KubeMind landing (`landing_8`)

Marketing site for **KubeMind** — self-hosted AI control plane. The router is branded **kmind**: purpose → intent → route.

## Naming

| Name | Role |
|------|------|
| **KubeMind** | Product / control plane (formerly Tricore) |
| **kmind** | The router — gives prompts a purpose, finds intent, routes with governance |
| mind / agents / sentinel | Sibling services in the plane |

## Run

Requires **Node 20+** (Next 15). Prefer nvm Node 22:

```bash
cd landing_8
nvm use 22
npm install
npm run dev
# http://localhost:3000
```

## Routes

| Path | Page |
|------|------|
| `/` | Home — brand, kmind pipeline, plane index, proof |
| `/kmind` | Intent router |
| `/mind` | Knowledge plane |
| `/agents` | Missions |
| `/sentinel` | Audit & observability |

## Positioning

- Brand-first hero: **KubeMind**
- Headline: *kmind gives your prompt a purpose, finds the intent, and routes it*
- Pipeline section (`#kmind`): Purpose → Intent → Route → Prove
- Control plane strip links to component pages
- Proof maps 1:1 to `make demo`
- Contrast vs LiteLLM / Portkey / Helicone / Langfuse

## Design notes

Ink / signal amber / seafoam — not purple gradients. Display: Syne. Body: Outfit. Mono: IBM Plex Mono. Hero is a full-bleed kmind routing mesh, not a card collage. Component pages share one shell: name hero, features, surface endpoints, prev/next.
