# KubeMind Python SDK (`kubemind-sdk`)

The official Python client library for **KubeMind** — the self-hosted intelligent AI gateway and governance control plane.

## Installation

```bash
pip install kubemind-sdk
```

## Quickstart

```python
from kubemind import KubeMindClient

# Initialize client with API key and workspace ID
client = KubeMindClient(
    api_key="your-api-key",
    workspace_id="default",
    router_url="http://localhost:9080",
    mind_url="http://localhost:9081",
    sentinel_url="http://localhost:9083",
)

# 1. Chat completion with intent classification & sensitivity governance
completion = client.chat_completion(
    model="llama3.1",
    messages=[
        {"role": "user", "content": "Email alice@example.com the summary report"}
    ]
)
print("Response:", completion["choices"][0]["message"]["content"])
print("Routing Decision:", completion.get("routing_decision"))

# 2. Semantic prompt routing
route = client.route("What is our company expense policy?")
print("Content:", route.get("content"))
print("Retrieval Status:", route.get("retrieval_status"))

# 3. CFO Cost & Usage Analytics
analytics = client.get_cost_analytics(window_hours=24)
print(f"Total Requests: {analytics['total_requests']}")
print(f"Estimated Spend ($): {analytics['estimated_spend_usd']}")

# 4. Cryptographic Ledger Verification
audit = client.verify_audit_ledger()
print("Ledger Intact:", audit.get("verified"))
```

## Features

- **Pre-Dispatch Sensitivity Gating**: Inline regex + local offline NER tokenization with in-memory reversible restoration.
- **Intent-Driven Routing**: Routes prompts dynamically based on classified semantic intent.
- **Fail-Closed Grounding**: Distinguishes verified corporate knowledge from hallucinations.
- **SHA-256 Tamper-Evident Ledger**: Verifiable cryptographic audit trail for HIPAA/SOC2 compliance.
- **Granular RBAC**: Supports role-scoped API keys (`admin`, `developer`, `auditor`, `viewer`).
