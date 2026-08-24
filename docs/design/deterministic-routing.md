# Deterministic and explainable routing

KubeMind separates advisory routing preferences from trusted policy
constraints. Preferences may influence ordering; constraints remove candidates
and always win.

## Stable reason codes

| Code | Meaning |
|---|---|
| `POLICY_ORDERED_SELECTION` | No valid preference changed the policy-defined order. |
| `PREFERRED_PROVIDER_ALLOWED` | The requested provider was eligible and selected. |
| `PREFERRED_PROVIDER_UNAVAILABLE` | The preference was allowed but unavailable or incompatible; the first eligible candidate was selected. |
| `POLICY_LOCAL_ONLY` | Sensitivity policy restricted dispatch to local providers. |
| `CLASSIFIER_LOW_CONFIDENCE_FALLBACK` | Intent classification abstained and used the general profile. |
| `CLASSIFIER_FAILURE_FALLBACK` | Classification failed safely and used the general profile. |
| `RETRIEVAL_UNAVAILABLE` | Knowledge profile could not reach Mind. Production fails closed (503). |

Reason codes are operational metadata, not provider quality claims. Native
provider errors, prompts, credentials, model responses, and internal exception
strings are excluded.

## Constraint order

The Runtime validates trusted tenant/Workspace/Project/Run identity, runtime
and operation, provider allowlist, data-region allowlist, deadline, budget
authority, Connection scope, model and capability scope before provider use.
A preferred provider outside an allowlist is denied; it is never converted into
an unconstrained fallback.

Data region comes from the trusted KeyMint Connection resolution, not from a
request or marketing catalog. A Connection whose region is absent from the
trusted Runtime allowlist fails with `POLICY_DENIED` before capability issue or
provider traffic. `global` and similar labels are identifiers, not evidence of
regulatory residency; operators must map them to verified provider contracts.

## Explainability payload

Successful direct-router responses include:

```json
{
  "routing_decision": {
    "reason_code": "POLICY_ORDERED_SELECTION",
    "considered_providers": ["ollama", "groq"],
    "eligible_providers": ["ollama"],
    "selected_provider": "ollama"
  }
}
```

Successful Runtime results use the contract's camelCase form and additionally
include the trusted selected Connection region. Provider names are safe catalog
identifiers; no endpoint URLs, Connection references, capability IDs, or keys
are included.

## Stability evidence

Golden test fixtures verify determinism across constraint evaluation, candidate ordering, and deterministic tie-breaking.
