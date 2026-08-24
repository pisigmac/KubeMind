# KubeMind Enterprise Architecture

**Product:** KubeMind — Kubernetes-Native AI Control Plane, Governance Gateway & Autonomous Infrastructure  
**Status:** Canonical Reference Architecture (Release v0.3.3)

---

## Core Value Proposition

Every prompt is evaluated and transformed in microsecond pipelines:
1. **Purpose Classification**: Adaptive soft-margin intent routing to optimal models or local instances.
2. **Zero-Egress Security & Privacy**: Inline Named Entity Recognition (NER) — regex + ONNX token classification — custom DLP dictionaries, and obfuscation-proof prompt injection defense.
3. **Reversible Pseudonymization**: In-memory tokenization before cloud dispatch and real-time de-anonymization over Server-Sent Events (SSE).
4. **Cryptographic Proof**: SHA-256 hash-chained tamper-evident audit ledger verification.
5. **Shared Identity & Billing**: OpenDesk RS256 JWT authentication + PayDeck Razorpay metered billing — fully decoupled from core routing logic.

---

## High-Level System Architecture

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

## Microservices Topology

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  kmind CLI  ·  Next.js Dashboard :9000 (/billing)  ·  landing (marketing)  │
├──────────────────────────────────────────────────────────────────────────────┤
│  router   :9080   Intent + Policy Gateway, SSE Streaming, KMS, MCP           │
│  mind     :9081   Knowledge Graph, pgvector Hybrid Search, Grounding          │
│  agents   :9082   Multi-Agent Swarm Orchestrator, Planning, Tool Runtime      │
│  sentinel :9083   SHA-256 Audit Ledger, OpenTelemetry Spans, WebSocket        │
├──────────────────────────────────────────────────────────────────────────────┤
│  Postgres (pgvector HNSW)  ·  Redis  ·  Ollama / On-Prem Inference            │
├──────────────────────────────────────────────────────────────────────────────┤
│  OpenDesk :8090   Shared RS256 JWT Identity & JWKS                            │
│  PayDeck  :8787   Shared Razorpay Billing (pd_live_ / pd_test_ keys)          │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Service | Port | Responsibilities |
|---------|------|------------------|
| **`router`** | `9080` | Unified AI gateway: rate limiting, Wasm hooks, local NER/DLP + ONNX NER, adaptive softmax routing, HNSW semantic cache, SSE stream de-anonymization, KMS credential management, and MCP server. |
| **`mind`** | `9081` | Enterprise organizational memory: pgvector hybrid vector + keyword retrieval with fail-closed grounding guarantees. Exposes `/v1/query` and `/v1/memory/query` alias. |
| **`agents`** | `9082` | Autonomous swarm execution: tool registry, direct tool invocation, and sync mission execution. |
| **`sentinel`** | `9083` | Cryptographic SHA-256 tamper-evident ledger, distributed trace ingestion, legal hold, and compliance verification. |
| **`dashboard`** | `9000` | Next.js 16 operator console with live CFO analytics, SHA-256 ledger integrity visualizer, Agent DAG workflow graph, and self-serve billing (`/billing`). |

---

## Request & Streaming Execution Pipeline

```
1. RBAC Authentication    Resolve workspace & verify granular role scopes (admin, developer, auditor, viewer)
                          Accepts X-API-Key or Authorization: Bearer <RS256 JWT from OpenDesk>
2. Pre-Dispatch Hooks     Execute custom WebAssembly / Python extensibility filters
3. Exact Cache Check      Instant lookup (<1ms) before embedding
4. Sensitivity & DLP      Offline NER (regex + ONNX token classification) + custom DLP regex & proprietary dictionary masking
5. Embed Once             Generate shared vector embedding for classification & semantic cache
6. Adaptive Intent Route  Softmax temperature scaling (T) and margin gating (code, rag, general, log, security)
7. Route Profile & Pool   Select candidate models (local-first vs cloud fallback) based on egress policy
8. HNSW Semantic Cache    Sub-millisecond cosine nearest-neighbor search with intent partitioning
9. Knowledge Grounding    Hybrid vector retrieval from Mind (503 fail-closed when Mind is down in production)
10. KMS Key Resolution    Zero-trust dynamic credential fetch from Vault, AWS Secrets Manager, or GCP
11. Model Execution:
    ├─ Non-Streaming:     Dispatch request, receive response, restore tokens in-memory
    └─ Streaming (SSE):   Pass chunks through StreamingDeAnonymizer sliding buffer to swap tokens live
12. Audit & Telemetry     Emit SHA-256 hash-chained entry to Sentinel ledger and Prometheus metrics
```

---

## Key Architectural Invariants

1. **Governance Independence**:
   * *A governance or DLP decision never depends on the intent classifier.*
   * Sensitivity and NER gating are hard controls; classifier failure falls back to `general` without bypassing policy.
2. **Zero-Egress Reversible Privacy**:
   * Sensitive entities (`[KM_PERSON_N]`, `[KM_ADDRESS_N]`, `[KM_DLP_N]`) are replaced with tokens before leaving the local cluster and reconstructed in memory on the return leg.
3. **Fail-Closed Grounding**:
   * If a prompt requires knowledge retrieval (`rag`) and Mind is unreachable, production returns **HTTP 503** rather than allowing the model to hallucinate.
4. **Zero Static Credentials**:
   * Cloud provider keys are resolved dynamically via KeyMint KMS adapters (Vault Kubernetes SA auth, AWS IAM, GCP Secret Manager) rather than static container environment variables.
5. **Cryptographic Proof of Compliance**:
   * Every routing decision, policy action, and model span is recorded in a sequential SHA-256 hash chain that can be independently verified via `kmind verify` or `GET /v1/audit/verify`.

---

## External Service Integrations

| Service | Protocol | Purpose |
|---------|----------|---------|
| **OpenDesk** (`:8090`) | RS256 JWT / JWKS | Shared identity & product grants — KubeMind validates `Authorization: Bearer <JWT>` against OpenDesk JWKS with zero DB call per request. The `roles.kubemind` claim maps to RBAC scopes (`admin`, `developer`, `auditor`, `viewer`). |
| **PayDeck** (`:8787`) | REST + Razorpay HMAC | Shared Razorpay billing — KubeMind creates orders via `pd_live_...` product keys, verifies HMAC payment signatures, and activates plan upgrades. Dashboard `/billing` page provides self-serve checkout. |

---

## Extensibility & Integration Protocols

* **Model Context Protocol (MCP)**: Native JSON-RPC stdio server exposing `kubemind_route`, `kubemind_mind_query`, `kubemind_mind_ingest`, and `kubemind_verify_audit` to Claude Desktop and Cursor IDE.
* **WebAssembly (Wasm) Hooks**: Microsecond pre- and post-dispatch filter hooks for bespoke regulatory compliance checks.
* **ONNX NER Engine**: `LocalNEREngine` runs ONNX token classification (`KUBEMIND_NER_ONNX_MODEL_PATH`) for higher-accuracy entity detection; falls back to regex when model not configured.
* **Client SDKs**: Official type-safe libraries for TypeScript (`@kubemind/sdk`) and Python (`kubemind-sdk`) including `getOrgAnalytics` / `get_org_analytics` for CFO cost reporting.
* **Cloud-Native Deployment**: Production Helm charts with PrometheusRule CRDs and Grafana Dashboards under `charts/kubemind/`.
