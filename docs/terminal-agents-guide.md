# Terminal Agents & Existing LLMs Integration Guide

**Product:** KubeMind AI Governance Gateway & Autonomous Control Plane  
**Target Audience:** Developers using terminal agents (Aider, Claude Code, Cline, Cursor Terminal), Python/TypeScript agent frameworks (LangChain, AutoGen, CrewAI), and direct LLM APIs (OpenAI, Anthropic, Gemini, Groq, local Ollama).

---

## 🎯 Architecture Overview

```
  ┌─────────────────────────────────────────────────────────────┐
  │       Your Terminal Agent / Coding Tool / Script            │
  │    (Aider, Claude Code, LangChain, Custom CLI, REPL)        │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                 Standard OpenAI / Anthropic REST
                    (base_url: http://localhost:9080/v1)
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │               KUBEMIND AI GATEWAY (:9080)                   │
  │                                                             │
  │  1. Tenant RBAC Authentication (X-API-Key / Bearer JWT)     │
  │  2. Inline Sensitivity Policy & Zero-Egress NER Masking     │
  │  3. Sub-Millisecond Exact & Semantic Cache (<2ms, $0 cost)  │
  │  4. Adaptive Softmax Intent Classifier (Code, RAG, Ops)     │
  │  5. Mind Knowledge Graph Retrieval (Fail-Closed RAG)        │
  │  6. KMS Credential Resolution (KeyMint / Direct Keys)       │
  │  7. Real-Time Streaming De-Anonymization (SSE Buffer)       │
  │  8. Cryptographic SHA-256 Audit Ledger Append (Sentinel)    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ OpenAI (GPT-4o)  │    │Anthropic (Claude)│    │Local Ollama/vLLM │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

Your terminal agent **never exposes raw customer PII or sensitive API tokens to external cloud providers**. All requests route through KubeMind on `localhost:9080`, where governance policies, caching, model selection, and cryptographic audit records execute inline.

---

## 📋 Step-by-Step Setup

### Step 1: Start the KubeMind Stack

Launch all KubeMind microservices using the operational startup utility:

```bash
cd /path/to/kubemind

# Create your environment file if not already present
cp .env.example .env

# Start all microservices in the background (Postgres, Redis, Router, Mind, Agents, Sentinel, Dashboard)
./scripts/start_all.sh
```

Verify that all services are online:
```bash
./scripts/status_all.sh
```

---

### Step 2: Configure Your Upstream Provider Keys

KubeMind requires your upstream provider keys so it can dispatch completions on your behalf.

Edit `.env` in the repository root:

```bash
nano .env
```

Add your provider keys under the **Cloud LLM Providers** section:

```env
# ── Cloud LLM Provider Keys ───────────────────────────────────────────
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Local Inference (Optional, free offline models) ───────────────────
OLLAMA_BASE_URL=http://localhost:11434
```

> **Zero-Trust Security Notice:** In local development (`KUBEMIND_CREDENTIAL_MODE=direct`), keys are read securely from deployment environment variables. In production (`KUBEMIND_CREDENTIAL_MODE=keymint`), keys are resolved dynamically from HashiCorp Vault, AWS Secrets Manager, or GCP Secret Manager with zero static keys stored in container configurations.

Restart the stack to apply changes:
```bash
./scripts/restart_all.sh
```

---

### Step 3: Registration & Workspace API Key Setup

KubeMind enforces multi-tenant workspace isolation. Each request must present an API key or OpenDesk Bearer token.

#### Option A: Local / Development Setup (Fastest)
In `.env`, define your API key and role:
```env
KUBEMIND_API_KEYS=my-terminal-key:default:admin
```
* **Format:** `<API_KEY>:<WORKSPACE_ID>:<ROLE>`
* **Roles:**
  * `admin`: Full access to all completions, routes, management tools, and org cost analytics.
  * `developer`: Chat completions, routing, classification, Mind memory queries & document ingestion.
  * `auditor`: Cryptographic SHA-256 audit ledger reads & verification.
  * `viewer`: Read-only telemetry and dashboard observation.

#### Option B: Self-Serve via Dashboard UI
1. Navigate to **`http://localhost:9000`** in your browser.
2. Sign in or register via OpenDesk.
3. Access **Settings → API Keys** to generate and manage keys.

---

### Step 4: Connecting Terminal Agents & Frameworks

Because KubeMind exposes an OpenAI-compatible REST interface on `:9080/v1`, connecting any terminal agent requires setting only two standard environment variables.

#### 1. Shell Environment (Global Export)
Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export OPENAI_API_BASE="http://localhost:9080/v1"
export OPENAI_API_KEY="my-terminal-key"
```

#### 2. `Aider` (AI Pair Programmer in the Terminal)
```bash
export OPENAI_API_BASE="http://localhost:9080/v1"
export OPENAI_API_KEY="my-terminal-key"

# Explicit model selection:
aider --model openai/gpt-4o

# Or auto-intent routing (KubeMind automatically picks the optimal model):
aider --model openai/auto
```

#### 3. `Claude Code` / Anthropic SDK Tools
KubeMind maps OpenAI-compatible requests and native Anthropic requests:
```bash
export ANTHROPIC_BASE_URL="http://localhost:9080/v1"
export ANTHROPIC_API_KEY="my-terminal-key"
```

#### 4. Python Agent Frameworks (LangChain, AutoGen, CrewAI, Custom)
```python
import os
from openai import OpenAI

# Initialize client pointing to KubeMind
client = OpenAI(
    base_url=os.environ.get("ROUTER_URL", "http://localhost:9080/v1"),
    api_key=os.environ.get("KUBEMIND_API_KEY", "my-terminal-key"),
)

# Standard chat completion call
response = client.chat.completions.create(
    model="gpt-4o",  # or "claude-3-5-sonnet", "llama3.1", "auto"
    messages=[
        {"role": "system", "content": "You are a cloud reliability assistant."},
        {"role": "user", "content": "Diagnose crashlooping pod with IP 10.244.0.12 in cluster prod-us-east."}
    ],
    temperature=0.2,
    stream=True,  # Full SSE streaming supported with real-time de-anonymization
)

for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

#### 5. TypeScript / Node.js Agents
```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: process.env.ROUTER_URL || "http://localhost:9080/v1",
  apiKey: process.env.KUBEMIND_API_KEY || "my-terminal-key",
});

async function run() {
  const completion = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: "Review database migration schema" }],
  });

  console.log(completion.choices[0].message.content);
}

run();
```

#### 6. Built-in Native CLI Agent (`kmind`)
KubeMind includes an official compiled Go CLI tool:

```bash
# Initialize local configuration
kmind init

# Launch real-time streaming REPL in terminal
kmind chat

# Monitor cluster throughput, active models, and cache savings
kmind top

# Verify the cryptographic SHA-256 audit ledger
kmind verify
```

---

### Step 5: Verification & End-to-End Test

Test that your terminal configuration is working:

```bash
curl -s http://localhost:9080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-terminal-key" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": "Patient Alice Henderson (SSN: 999-12-3456, email: alice.h@domain.com) requested record transfer."
      }
    ]
  }'
```

#### Verification Checklist:
1. **PII Masking**: Check logs (`docker compose logs router`) — verify `Alice Henderson`, SSN, and email were masked to tokens (`[KM_PERSON_1]`, `[KM_DLP_1]`, `[KM_EMAIL_1]`) *before* outbound provider dispatch.
2. **Reversible Restoration**: The returned response contains the restored names.
3. **Audit Ledger**: Run `./scripts/verify_ledger.sh` to confirm a tamper-evident SHA-256 entry was recorded in Sentinel.
