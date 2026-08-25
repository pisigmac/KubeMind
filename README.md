# KubeMind

**Kubernetes-Native AI Governance Gateway & Autonomous Control Plane**  
*Release v0.3.3 · Production Ready · Air-Gapped & Cloud-Native*

---

## 🌟 Core Value Proposition

KubeMind intercepts, evaluates, transforms, and routes LLM requests through sub-millisecond governance pipelines:

1. **Adaptive Intent Routing**: Softmax temperature-scaled semantic classification routing prompts to optimal local or cloud models.
2. **Zero-Egress Reversible Privacy**: Inline Named Entity Recognition (Local Regex + ONNX Token Classification) that masks PII/secrets (`[KM_PERSON_1]`, `[KM_EMAIL_1]`) before dispatch and restores them in real-time over SSE streams.
3. **Fail-Closed Memory Grounding**: Mind hybrid vector knowledge retrieval (`pgvector` HNSW) that strictly returns `HTTP 503` if retrieval fails rather than allowing hallucinations.
4. **Cryptographic SHA-256 Audit Ledger**: Every routing decision, span, and policy action is appended to an immutable, tamper-evident cryptographic hash-chain.
5. **Decoupled Identity & Billing**: Native RS256 JWT validation against **OpenDesk** JWKS and self-serve metered Razorpay checkout via **PayDeck**.

---

## 🏛️ High-Level System Architecture

```
                               ┌──────────────────────────────────────────────────────────┐
                               │               KUBEMIND ENTERPRISE PLATFORM               │
                               │                  Release v0.3.3 (master)                 │
                               └────────────────────────────┬─────────────────────────────┘
                                                            │
                ┌───────────────────┬───────────────────────┼───────────────────────┬───────────────────┐
                │                   │                       │                       │                   │
                ▼                   ▼                       ▼                       ▼                   ▼
        ┌──────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
        │ Gateway & Policy │ │ Cloud Security    │ │ Autonomous Agents │ │ Ops & Monitoring  │ │ Client Ecosystem  │
        │ ──────────────── │ │ ───────────────── │ │ ───────────────── │ │ ───────────────── │ │ ───────────────── │
        │ • Local NER DLP  │ │ • 4-Tier RBAC     │ │ • Multi-Agent     │ │ • kmind top TUI   │ │ • @kubemind/sdk   │
        │ • ONNX NER Model │ │ • OpenDesk JWKS   │ │   Swarm Pipeline  │ │ • kmind chat REPL │ │   (TypeScript)    │
        │ • SSE Streaming  │ │ • HashiCorp Vault │ │ • Native MCP      │ │ • PrometheusRules │ │ • kubemind-sdk    │
        │ • HNSW pgvector  │ │ • AWS Secrets     │ │   Server (Claude) │ │ • Grafana HUD     │ │   (Python)        │
        │ • Wasm Hooks     │ │ • SHA-256 Ledger  │ │ • Sandboxed Tools │ │ • Next.js UI DAG  │ │ • Linux/Mac CLIs  │
        │ • Adaptive T-Soft│ │ • PayDeck Billing │ │ • Tool Invocation │ │ • Billing /billing│ │ • kmind fetch-    │
        └──────────────────┘ └───────────────────┘ └───────────────────┘ └───────────────────┘ │   models CLI      │
                                                                                                 └───────────────────┘
```

---

## ⚡ Request Execution & Zero-Egress Pipeline Flow

```
User Prompt (REST / SSE / SDK)
  │
  ├─► 1. RBAC & Tenant Verification
  │      • Evaluates X-API-Key or OpenDesk RS256 Bearer JWT against public JWKS
  │      • Cryptographically binds request to Workspace (admin, developer, auditor, viewer)
  │
  ├─► 2. Security & Inline Policy Engine (Runs BEFORE Classifier)
  │      • Secret Key Block: Rejects RSA keys, AWS/GCP API tokens with HTTP 403
  │      • Privacy NER Engine: Local Regex + ONNX Bert NER masks names, emails, addresses into [KM_*]
  │      • Prompt Injection Filter: Heuristic adversarial score tagging
  │
  ├─► 3. Semantic & Exact Caching Check
  │      • Sub-millisecond exact hash & cosine nearest-neighbor lookup in Redis / pgvector
  │      • Bypassable with X-KubeMind-Cache: bypass
  │
  ├─► 4. Adaptive Intent Classification & Profile Matching
  │      • Soft-margin intent categorization (code, rag, general, log, security)
  │      • Selects provider pool and fallback cascade chain
  │
  ├─► 5. Mind Knowledge Graph Retrieval
  │      • Retrieves relevant semantic embeddings and relational context from Mind (:9081)
  │      • Fail-Closed: Outage in production returns 503 instead of risking hallucination
  │
  ├─► 6. LLM Provider Dispatch & Dynamic KMS Credential Resolution
  │      • Dispatches pseudonymized prompt to local Ollama/vLLM or Cloud Provider (KeyMint/Vault)
  │
  ├─► 7. Reversible Token Restoration & Streaming Engine
  │      • Non-Streaming: Swaps [KM_*] tokens back to original values in JSON response
  │      • Streaming (SSE): Sliding window StreamingDeAnonymizer restores entities in live token chunks
  │
  └─► 8. Cryptographic Audit Ledger & Telemetry
         • Appends SHA-256 hash-chained receipt to Sentinel (:9083)
         • Emits OpenTelemetry spans & Prometheus counters (kubemind_spans_ingested_total)
```

---

## 🧩 Microservices Topology

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  kmind CLI  ·  Next.js Dashboard :9000 (/billing)  ·  landing (marketing)   │
├──────────────────────────────────────────────────────────────────────────────┤
│  router   :9080   Intent + Policy Gateway, SSE Streaming, KMS, MCP           │
│  mind     :9081   Knowledge Graph, pgvector Hybrid Search, Grounding          │
│  agents   :9082   Multi-Agent Swarm Orchestrator, Planning, Tool Runtime      │
│  sentinel :9083   SHA-256 Audit Ledger, OpenTelemetry Spans, WebSocket        │
├──────────────────────────────────────────────────────────────────────────────┤
│  Postgres 16 (pgvector HNSW)  ·  Redis 7  ·  Ollama / On-Prem Inference       │
├──────────────────────────────────────────────────────────────────────────────┤
│  OpenDesk :8090   Shared RS256 JWT Identity & JWKS Verification               │
│  PayDeck  :8787   Shared Razorpay Metered Billing Engine                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Service | Port | Key Features & Responsibilities |
|---------|------|---------------------------------|
| **`router`** | `9080` | Unified AI gateway: rate limiting, Wasm hooks, local NER/DLP + ONNX NER, adaptive softmax routing, HNSW semantic cache, SSE stream de-anonymization, KMS credential management, and MCP server. |
| **`mind`** | `9081` | Enterprise organizational memory: pgvector hybrid vector + keyword retrieval with fail-closed grounding guarantees (`/v1/query`, `/v1/memory/query`, `/v1/graph`). |
| **`agents`** | `9082` | Autonomous swarm execution: tool registry (`/v1/tools`), direct tool invocation (`/v1/tools/invoke`), and sync/async mission planner (`/v1/missions`). |
| **`sentinel`** | `9083` | Cryptographic SHA-256 tamper-evident ledger, distributed trace ingestion, legal hold, audit exports (`/v1/export`), and Prometheus metrics (`/metrics`). |
| **`dashboard`** | `9000` | Next.js 16 operator console with live CFO analytics, SHA-256 ledger integrity visualizer, Agent DAG workflow graph, and self-serve billing (`/billing`). |

---

## 🚀 Quickstart

### 1. Launch the Stack

```bash
cp .env.example .env
make up
make status
```

### 2. Verify Health Across All Services

```bash
curl -s http://localhost:9080/health  # Router
curl -s http://localhost:9081/health  # Mind
curl -s http://localhost:9082/health  # Agents
curl -s http://localhost:9083/health  # Sentinel
```

### 3. Run Intent Classification & Gateway Routes

```bash
# Dry-run intent classification (no LLM dispatch)
curl -s http://localhost:9080/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Write a Python script to compute fibonacci numbers"}'

# Zero-Egress PII Masking & Reversible Restoration
curl -s http://localhost:9080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "llama3.1",
    "messages": [{"role": "user", "content": "Doctor Alice Smith sent records to bob@corp.org"}]
  }'
```

### 4. Fetch ONNX NER Models

```bash
kmind fetch-models   # Downloads ONNX NER weights to ~/.kubemind/models/
```

---

## 🧪 Comprehensive Automated Test Utility

Run the complete 20-step end-to-end integration test suite:

```bash
./scripts/e2e_curl_test.sh
```

Logs are written to `logs/latest.log` with full request and response traces.

---

## 📦 Client SDKs

- **Python SDK (`kubemind-sdk`)**: [`sdk/python/`](sdk/python) · `pip install kubemind-sdk`
- **TypeScript / Node.js SDK (`@kubemind/sdk`)**: [`sdk/typescript/`](sdk/typescript) · `npm install @kubemind/sdk`
- **Interactive Walkthroughs**: [`examples/`](examples) (Python & TypeScript demos)

---

## 📖 Documentation Index

| Document | Description |
|----------|-------------|
| [docs/terminal-agents-guide.md](docs/terminal-agents-guide.md) | Terminal Agents (Aider, Claude Code, Python) & Existing LLMs Integration |
| [docs/architecture.md](docs/architecture.md) | Canonical Reference Architecture & System Topology |
| [docs/api.md](docs/api.md) | Complete Public API & `kmind` CLI Inventory |
| [docs/integration.md](docs/integration.md) | OpenDesk Identity & PayDeck Billing Integration Guide |
| [docs/credential-modes.md](docs/credential-modes.md) | KeyMint Zero-Trust vs Direct Credential Modes |
| [charts/kubemind/README.md](charts/kubemind/README.md) | Production Kubernetes Helm Chart Configuration |

---

## 📄 License

MIT © 2026 KubeMind Authors.
