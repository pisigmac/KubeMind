# @kubemind/sdk

The official TypeScript/Node.js client SDK for **KubeMind** — the self-hosted intelligent AI gateway and governance control plane.

## Installation

```bash
npm install @kubemind/sdk
```

## Quickstart

```typescript
import { KubeMindClient } from "@kubemind/sdk";

// Initialize client
const client = new KubeMindClient({
  apiKey: "your-workspace-api-key",
  workspaceId: "default",
  routerUrl: "http://localhost:9080",
  mindUrl: "http://localhost:9081",
  sentinelUrl: "http://localhost:9083",
});

async function main() {
  // 1. Chat completion with intent routing & sensitivity policy
  const completion = await client.chatCompletion({
    model: "llama3.1",
    messages: [
      { role: "user", content: "Write a python function to parse YAML" }
    ],
  });

  console.log("Response:", completion.choices[0].message?.content);
  console.log("Routing Decision:", completion.routing_decision);

  // 2. Semantic prompt routing
  const routeRes = await client.route({
    prompt: "What is our company expense policy?",
  });
  console.log("Content:", routeRes.content);
  console.log("Retrieval Status:", routeRes.retrieval_status);

  // 3. Ingest knowledge into Mind
  await client.ingestMemory({
    content: "Expenses under $50 do not require receipts.",
    source: "handbook",
  });

  // 4. Cryptographically verify the tamper-evident audit ledger
  const audit = await client.verifyAuditLedger();
  console.log("Ledger Verified:", audit.verified);
}

main();
```

## Features

- **Pre-Dispatch Sensitivity Gating**: Inline regex + local offline NER tokenization with in-memory reversible restoration.
- **Intent-Driven Routing**: Routes prompts based on classified intent and constraint profiles.
- **Fail-Closed Grounding**: Distinguishes verified corporate knowledge from ungrounded hallucinations.
- **SHA-256 Tamper-Evident Ledger**: Cryptographic non-repudiation and verification.
- **Zero External Dependencies**: Works seamlessly in Node.js (>= 18), Next.js, Edge Runtimes, Bun, and Deno.
