# Tricore End-to-End Production Verification Suite (`test.md`)

This document provides a comprehensive, production-grade test suite for the **Tricore** unified AI builder stack. Follow these step-by-step procedures to validate service health, inter-service communication, data ingestion, LLM routing, agent execution, telemetry collection, and dashboard functionality.

---

## Architecture Quick Reference & Port Mapping

| Service | Internal Port | Host Port | Protocol | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`dashboard`** | `3000` | **`9000`** | HTTP | Next.js Web UI & Real-Time Monitoring |
| **`router`** | `8080` | **`9080`** | HTTP | LLM Gateway, Model Routing, Caching & Circuit Breaker |
| **`mind`** | `8081` | **`9081`** | HTTP | Knowledge Graph, Embeddings & Hybrid Search |
| **`agents`** | `8082` | **`9082`** | HTTP | Agent Execution Engine, Planning & Tool Invocation |
| **`sentinel`** | `8083` | **`9083`** | HTTP/WS | Telemetry Span Ingestion, Metrics & WebSocket Streaming |
| **`postgres`** | `5432` | **`9432`** | TCP | Relational Storage for Missions, Usage & Memory |
| **`redis`** | `6379` | **`9379`** | TCP | Caching & Rate Limiting |
| **`ollama`** | `11434` | **`9434`** | HTTP | Local LLM Inference Engine |

---

## Phase 1: Environment & Service Health Checks

Verify that all Docker containers are running, database connections are active, and endpoints report healthy.

### Step 1.1: Verify Docker Stack Status
```bash
docker compose ps
```
**Expected Output**: All 8 containers (`postgres`, `redis`, `ollama`, `router`, `mind`, `agents`, `sentinel`, `dashboard`) should show state `Up` or `Healthy`.

### Step 1.2: Validate Microservice Health Endpoints
Run the aggregated health verification command:

```bash
make status
```

Or test each service individually via `curl`:

```bash
# 1. Router Health
curl -s http://localhost:9080/health | jq .

# 2. Mind Health
curl -s http://localhost:9081/health | jq .

# 3. Agents Health
curl -s http://localhost:9082/health | jq .

# 4. Sentinel Health
curl -s http://localhost:9083/health | jq .

# 5. Dashboard HTTP Response
curl -s -I http://localhost:9000 | grep "HTTP/"
```

**Expected Results**:
- All `/health` endpoints must return HTTP 200 with `"status": "healthy"`.
- Dashboard must return `HTTP/1.1 200 OK`.

---

## Phase 2: Router Service Testing (LLM Gateway & Caching)

Test LLM provider routing, health checking, usage analytics, and response caching.

### Step 2.1: Check Registered Provider Health
```bash
curl -s http://localhost:9080/v1/providers/health | jq .
```
**Expected Result**:
```json
[
  {
    "name": "ollama",
    "healthy": true,
    "circuit_state": "closed",
    "models": ["llama3.1", "mistral", "nomic-embed-text"],
    "priority": 1,
    "free": true,
    "failure_count": 0
  }
]
```

### Step 2.2: Test Chat Completion Routing
Send a prompt through the Gateway:

```bash
curl -s -X POST http://localhost:9080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  -d '{
    "model": "llama3.1",
    "messages": [
      {"role": "system", "content": "You are a concise assistant."},
      {"role": "user", "content": "Say hello in 3 words."}
    ],
    "temperature": 0.2
  }' | jq .
```
**Expected Result**: Valid JSON response containing `choices[0].message.content` and metadata indicating the provider used.

### Step 2.3: Test Redis Caching
Re-run the exact same `curl` command above.
**Expected Result**: The second response should include `"cached": true` and return near-instantaneously (<10ms).

### Step 2.4: Check Usage Analytics
```bash
curl -s http://localhost:9080/v1/usage -H "X-Workspace-ID: default" | jq .
```
**Expected Result**: `total_requests` incremented, showing token counts per workspace.

---

## Phase 3: Mind Service Testing (Knowledge & Search)

Test document ingestion, graph storage, and hybrid vector search.

### Step 3.1: Check Knowledge Node Types & Schemas
```bash
curl -s http://localhost:9081/v1/types | jq .
```

### Step 3.2: Ingest Code / Document Nodes
Ingest a document into the Knowledge store:

```bash
curl -s -X POST http://localhost:9081/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  -d '{
    "source": "/app/Dockerfile",
    "type": "code"
  }' | jq .
```
**Expected Result**: Response returning `"ingested": 1` with generated `node_ids`.

### Step 3.3: Perform Hybrid Knowledge Query
Query the Knowledge graph for ingested content:

```bash
curl -s -X POST http://localhost:9081/v1/query \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  -d '{
    "query": "Dockerfile uvicorn entrypoint",
    "top_k": 5
  }' | jq .
```
**Expected Result**: Array of matched nodes with vector and keyword search scores.

### Step 3.4: Export Knowledge Subgraph
```bash
curl -s http://localhost:9081/v1/graph -H "X-Workspace-ID: default" | jq .
```

---

## Phase 4: Agents Service Testing (Execution & Planning)

Test tool registry, mission creation, task planning, and step execution.

### Step 4.1: List Available Agent Tools
```bash
curl -s http://localhost:9082/v1/tools | jq .
```
**Expected Result**: Array of available execution tools (`filesystem`, `shell`, `web_search`, `knowledge`, `code_analyzer`, `read_file`, `write_file`).

### Step 4.2: Execute a Tool Directly
Test the `filesystem` tool:

```bash
curl -s -X POST http://localhost:9082/v1/tools/invoke \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  -d '{
    "tool": "read_file",
    "arguments": {
      "path": "/app/Dockerfile"
    }
  }' | jq .
```

### Step 4.3: Run an Agent Mission (Sync Mode)
Create and run a multi-step agent mission:

```bash
curl -s -X POST http://localhost:9082/v1/missions \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  -d '{
    "prompt": "Create a file named test_output.txt with content Hello Tricore",
    "mode": "sync"
  }' | jq .
```
**Expected Result**:
- Response containing `"status": "completed"`.
- Execution steps generated by `planner`, tool call log, and total tokens used.

### Step 4.4: List Missions History
```bash
curl -s http://localhost:9082/v1/missions -H "X-Workspace-ID: default" | jq .
```

---

## Phase 5: Sentinel Service Testing (Observability & Tracing)

Test span ingestion, telemetry querying, aggregated metrics, and WebSocket streaming.

### Step 5.1: Ingest a Custom Telemetry Span
```bash
curl -s -X POST http://localhost:9083/v1/spans \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "test-trace-001",
    "span_id": "test-span-001",
    "workspace_id": "default",
    "service": "agents",
    "operation": "mission_execution",
    "status": "ok",
    "start_time": "2026-07-25T23:59:00Z",
    "attributes": {
      "duration_ms": 142.5,
      "mission_id": "m-1234"
    }
  }' | jq .
```
**Expected Result**: `{"status": "ok", "span_id": 1}`.

### Step 5.2: Query Telemetry Spans
```bash
curl -s "http://localhost:9083/v1/spans?workspace_id=default&limit=10" | jq .
```

### Step 5.3: Fetch Aggregated Metrics
```bash
curl -s "http://localhost:9083/v1/metrics?workspace_id=default&hours=24" | jq .
```

### Step 5.4: Test Sentinel WebSocket Real-Time Stream
Using `wscat`:

```bash
wscat -c ws://localhost:9083/v1/stream
```
When connected, send a subscription message:
```json
{"type": "subscribe", "workspace_id": "default"}
```
**Expected Result**: Real-time span notifications and heartbeat ping/pongs broadcast from Sentinel.

---

## Phase 6: Dashboard End-to-End Verification

Verify that the Next.js Web Dashboard loads and connects to all microservices.

1. Open your browser and navigate to: **`http://localhost:9000`**
2. **Overview Page (`/`)**: Verify that `Router`, `Mind`, `Agents`, and `Sentinel` all display green **Healthy** badges.
3. **Gateway Page (`/gateway`)**: Verify provider list, Ollama status, priority, and circuit breaker states. Click **Clear Cache** and confirm success.
4. **Knowledge Page (`/knowledge`)**: Perform a search for `"Dockerfile"` and verify results populate from Mind.
5. **Agents Page (`/agents`)**: Enter a prompt (e.g. `"List files in current directory"`) and click **Run**. Verify mission history updates in real-time.
6. **Observability Page (`/observability`)**: Verify the **● Live** status indicator is green and trace table populates with recent spans.

---

## Automated Quick Verification Script

Save the following one-liner to verify all endpoints in sequence:

```bash
echo "=== TRICORE E2E VERIFICATION ===" && \
curl -sf http://localhost:9080/health && echo " -> Router OK" && \
curl -sf http://localhost:9081/health && echo " -> Mind OK" && \
curl -sf http://localhost:9082/health && echo " -> Agents OK" && \
curl -sf http://localhost:9083/health && echo " -> Sentinel OK" && \
curl -sf -I http://localhost:9000 > /dev/null && echo " -> Dashboard OK" && \
echo "=== ALL SERVICES OPERATIONAL ==="
```
