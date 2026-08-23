# KubeMind Release Notes & Changelog

All notable changes to the KubeMind AI Gateway & Autonomous Infrastructure platform are documented in this file.

---

## [v0.3.0] - 2026-08-24

### 🚀 Major Features & Architectural Milestones

#### 1. Zero-Egress Reversible Local NER Pseudonymization
* **In-Memory Entity Redaction**: Offline Named Entity Recognition (NER) tokenizes person names (`[KM_PERSON_1]`), physical addresses (`[KM_ADDRESS_1]`), and organizations (`[KM_ORGANIZATION_1]`) using local regex and ONNX models before cloud dispatch.
* **Bi-Directional Response Restoration**: In-memory token mapping reconstructs original entities on the return leg, ensuring third-party providers never store or train on raw enterprise PII.

#### 2. Real-Time Streaming SSE De-Anonymization
* **Chunk Lookahead Buffering**: High-performance streaming sliding window buffer (`StreamingDeAnonymizer`) detects and swaps pseudonymized tokens on-the-fly over Server-Sent Events (SSE) without introducing human-perceptible latency or fragmenting tokens.
* **Unified SDK Streaming**: `client.chat_stream()` in Python and `client.chatStream()` in TypeScript.

#### 3. Granular 4-Tier RBAC Permission Engine
* **Role Hierarchy**: Strict scope-based gating across all gateway, mind, agent, and sentinel endpoints:
  * `admin`: Complete administrative wildcard access (`*`).
  * `developer`: Prompt routing, chat completions, knowledge ingestion, and usage metrics (`chat`, `route`, `classify`, `mind:query`, `mind:ingest`, `usage:read`).
  * `auditor`: Cryptographic ledger verification and audit reading (`audit:read`, `audit:verify`, `usage:read`).
  * `viewer`: Read-only metrics and dashboard observation (`metrics:read`, `dashboard:read`, `usage:read`).

#### 4. CFO Financial Analytics & Live Telemetry
* **Cost & Token Rollups**: `/v1/usage/analytics` endpoint providing rolling window (24h/7d/30d) token breakdowns and dollar spend per provider.
* **Interactive Next.js Dashboard**: Live financial charts, cost graphs, and cryptographic SHA-256 ledger integrity visualizers.

#### 5. Modernized `kmind` Go CLI
* **Interactive Streaming REPL**: `kmind chat [model]` for real-time streaming conversations directly from the terminal.
* **Live Terminal TUI Cluster Monitor**: `kmind top` (or `kmind monitor`) displaying live QPS, latency EWMA, provider circuit breaker states, and token volume.
* **Operational Commands**: `kmind analytics`, `kmind verify`, `kmind agent`, and `kmind knowledge`.

#### 6. Multi-Tenant Semantic Cache Index Tuning
* **HNSW Vector Acceleration**: Integrated Hierarchical Navigable Small World (HNSW) cosine index acceleration in Postgres `pgvector` for sub-millisecond semantic similarity lookups.

#### 7. Agent Mission DAG Graph Visualization
* **Visual Mission Flowchart**: Interactive DAG execution graph in the Operator Dashboard tracing intent classification, knowledge graph grounding, tool execution, and ledger span emission.

---

### 📦 Client Libraries & Packaging
* **Python SDK (`kubemind-sdk`)**: Available via PyPI with full pyproject.toml and wheel builds.
* **TypeScript SDK (`@kubemind/sdk`)**: Available via npm with native ESM/CJS typings.
* **Multi-Language CI/CD Pipeline**: GitHub Actions matrix validating Python 3.10/3.11, Node.js 22, Go 1.22, Next.js, and automated E2E test suites.
