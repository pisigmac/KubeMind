# KubeMind shared schemas

**Purpose:** Single place for cross-service request/response contracts used by SDKs, CLI, and docs.  
**Product:** KubeMind  
**Format (Phase 0 decision):** JSON Schema (Draft 2020-12) skeletons, owned per service.

## Ownership

| Schema file | Owner service | Notes |
|-------------|---------------|--------|
| `chat-request.json` | router | OpenAI-compatible chat |
| `route-request.json` | router | Planned Phase 1 `/v1/route` |
| `embeddings-request.json` | router | Embeddings body |
| `query-request.json` | mind | Hybrid search |
| `memory-query-request.json` | mind | Planned alias Phase 2 |
| `ingest-request.json` | mind | Knowledge ingest |
| `mission-request.json` | agents | Mission create |
| `task-dispatch-request.json` | agents | Planned alias Phase 4 |
| `span-ingest.json` | sentinel | Trace span ingest |

Service implementation remains source of runtime validation (Pydantic). Schemas here are the **portable contract** for SDKs and external consumers.

## Rules

1. Breaking changes require a version bump note in this README and an entry in `docs/api.md`.  
2. SDKs (Phase 6) should not invent fields absent from these schemas + `docs/api.md`.  
3. Planned (`route-request`, etc.) schemas may exist before the endpoint ships; mark `"x-kubemind-status": "planned"` in the schema.  
4. Do not put secrets or environment-specific URLs in schemas.

## Layout

```text
shared/schemas/
  README.md                 # this file
  chat-request.json
  route-request.json
  embeddings-request.json
  query-request.json
  memory-query-request.json
  ingest-request.json
  mission-request.json
  task-dispatch-request.json
  span-ingest.json
```

## Validation (later)

CI may later run `check-jsonschema` or similar against fixtures. Not required for Phase 0.

## Related

- Human API inventory: [`docs/api.md`](../../docs/api.md)  
- Naming: [`docs/adr/0001-kubemind-naming.md`](../../docs/adr/0001-kubemind-naming.md)  
- Implementation plan: [`docs/KUBEMIND_IMPLEMENTATION_PLAN.md`](../../docs/KUBEMIND_IMPLEMENTATION_PLAN.md)
