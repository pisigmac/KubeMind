# KubeMind Examples & Demos

Interactive walk-throughs and code samples demonstrating KubeMind's core capabilities in Python and TypeScript.

## Prerequisites

Start the local KubeMind cluster:
```bash
make up
```

## Python Demo

```bash
# 1. Install local SDK
pip install -e sdk/python

# 2. Run governance & security demo
python3 examples/python/demo_security_and_governance.py
```

## TypeScript / Node.js Demo

```bash
# 1. Compile TypeScript SDK
./scripts/build.sh --sdk

# 2. Run TypeScript walkthrough
npx ts-node examples/typescript/demo_routing_and_governance.ts
```

## What These Demos Cover

1. **Pre-Dispatch Sensitivity Gating & Reversible Pseudonymization**: Zero-egress local NER tokenization that protects patient/customer data from ever reaching third-party cloud LLMs.
2. **Fail-Closed Grounding**: Distinguishes verified corporate knowledge from ungrounded hallucinations with explicit 503 protection when vector memories are unavailable.
3. **CFO Financial Analytics**: Programmatic retrieval of aggregated token usage, provider distribution, and dollar spend.
4. **Cryptographic Ledger Non-Repudiation**: Instant mathematical verification of SHA-256 hash chains across all audit logs.
