# Intent-aware routing with enforced governance

**Service:** router
**Status:** Implemented
**Related:** [semantic-cache.md](semantic-cache.md), [ADR 0001](../adr/0001-kubemind-naming.md)

Two questions are asked of every prompt, and the router is the only place both
can be answered before the prompt goes anywhere.

- **Purpose** — what is this request for? Selects the cheapest capable target.
- **Sensitivity** — what is in it? Constrains which targets are eligible.

## Design invariant

**A governance decision never depends on the intent classifier.**

Intent is an optimisation: being wrong costs money or answer quality, and it is
allowed to abstain. Sensitivity is a control: being wrong is a breach, so it is
tuned for recall and never abstains.

The tempting shortcut is `if intent == "security": local_only`. That would make
the compliance guarantee only as strong as a classifier's F1 score. The two
passes share an embedding and a decision point, and nothing else. `router.policy`
does not import `router.intent`.

## Pipeline order

```
1. Auth              workspace derived from the API key, not the header
2. Exact cache       returns here; no embedding is computed on this path
3. Sensitivity       PII, secrets and injection over the raw text
4. Embed once        one vector, reused below
5. Intent            k-NN over example embeddings, with rules as a prior
6. Profile           intent selects model, pool, params, cache policy
7. Policy overlay    narrows the eligible pool, or blocks
8. Semantic cache    scoped to the intent partition and a model signature
9. Retrieval         retrieval-intent prompts are augmented from mind
10. Dispatch         walk the route chain
11. Decision record  emitted to sentinel
```

Step 2 comes before step 4 deliberately. An exact hit costs about 1ms; putting
the embedder in front of it would add 10-40ms to the fastest path the router
has. The consequence is that an exact hit cannot classify, which is why intent
is persisted on cache entries and read back rather than recomputed.

## The classifier

Hybrid, in two layers.

**Rules** are a high-precision prior, narrowed to discriminative phrases. The
previous implementation matched bare tokens like `api` and `sdk`, which appear
in plenty of prompts that have nothing to do with code. A small set are hard
overrides (`CrashLoopBackOff`, a CVE identifier) that settle the intent without
consulting the semantic layer.

**k-NN over example embeddings** carries generalisation. Centroids were
rejected: an intent like `code` is genuinely multi-modal — write, debug and
explain occupy different regions, and their mean lands between them, matching
nothing well. Each intent is scored on the mean of *its own* top-k similarities,
so an intent with many examples cannot crowd out one with few.

### Confidence and abstention

Confidence is the **margin** between the top two intents, not raw similarity.
Embedding spaces are anisotropic and everything sits at 0.5-0.8 similarity to
everything, so absolute similarity says little about certainty.

Three ways to abstain to `general`:

- margin below `margin_threshold`
- top score below `min_similarity`
- the `_background` decoy class wins

The decoy class is a set of ordinary prompts that belong to no real intent. It
gives out-of-distribution traffic somewhere to land instead of being forced into
the nearest real intent.

Rule ties also abstain. The old classifier resolved them by dictionary order,
which meant a tie silently became `code`.

If the embedder is unavailable the classifier degrades to rules only. A broken
Ollama should cost routing quality, not availability.

## Adding an intent

No code. Add examples and point at a profile:

```yaml
routing:
  intents:
    incident_triage:
      profile: fast_local
      examples:
        - "why is this pod crashlooping"
        - "summarize the error spike in checkout"
```

The index is built at startup by embedding each example.

## Profiles

An intent selects a profile, not a provider. Mapping straight to a provider name
left the model, parameters and cache behaviour unspecified, so the routing
decision was only half made.

```yaml
routing:
  profiles:
    code:
      pool: [deepseek_local, ollama, groq]   # order is preference
      temperature: 0.2
      system_prompt: "You are a precise software engineer..."
      cache:
        distance_threshold: 0.02             # tighter than general chat
```

Pool order is an explicit statement of preference and is preserved. Without a
pool, ordering falls back to the cost policy: free first, then priority.

Legacy `prefer_targets: {intent: provider}` still works; each entry becomes a
single-provider pool.

## The policy overlay

Runs inline, before dispatch. Sentinel's copy of the same detectors runs at span
ingest, which is *after* the prompt reached the provider — useful for reporting,
useless as a control. Both import `kubemind_policy`, so a rule change cannot
make them disagree.

```yaml
policy:
  enabled: true
  fail_closed: true
  default:
    rules:
      - detector: private_key
        action: block
      - detector: bearer
        action: redact
      - detector: injection
        threshold: 0.6
        action: block
      - detector: any_pii
        action: local_only
```

Actions, most restrictive wins: `allow` < `redact` < `local_only` < `block`.
Redaction still applies underneath `local_only`, because sending less is better
even when the destination is inside the cluster.

`local_only` drops the eligible pool to providers flagged `local: true`. **If no
healthy local provider exists the request is refused with 503.** Falling back to
a cloud provider would defeat the verdict, so this is the one constraint that
never degrades. An unsatisfiable *pool* falls back; an unsatisfiable *egress
class* does not.

Sensitive prompts are not cached.

## Cache interaction

- **Model signature.** Entries match only when model, system prompt and
  temperature hash identically. Previously a `llama3.1` answer could satisfy a
  `gpt-4o` request.
- **Intent partitioning.** Confident classifications read and write an
  intent-scoped key, which shrinks each scan and stops a `code` prompt matching
  a `general` one. A misclassification costs a cache miss, not a wrong answer.
  Low-confidence requests use the shared bucket and read both.
- **Stored intent.** Written so exact hits can report it truthfully.

## Evaluation

```bash
make eval          # score against the held-out labelled set
make eval-sweep    # accuracy versus abstention across thresholds
make eval-ci       # non-zero exit if any policy miss
```

The dataset in `services/router/eval/dataset.jsonl` is held out from the
examples that build the index; scoring on the examples themselves measures
memorisation.

Errors are weighted by consequence rather than averaged:

| error | weight | meaning |
|---|---|---|
| `policy_miss` | 25.0 | sensitive content under-enforced |
| `policy_false_positive` | 2.0 | over-enforced |
| `misroute` | 1.0 | wrong intent |
| `missed_abstention` | 0.5 | guessed on an ambiguous prompt |
| `over_abstention` | 0.3 | abstained when it could have routed |

Plain accuracy averages away exactly the errors that matter. **`policy_miss`
must be zero**; `make eval-ci` fails the build otherwise.

Pick thresholds from the sweep table, not by feel.

## Inspecting decisions

```bash
# Dry run: classify and evaluate policy without dispatching or paying
curl -s localhost:9080/v1/classify -d '{"prompt":"why is my pod crashlooping"}'

# What the classifier knows and where each intent routes
curl -s localhost:9080/v1/intents

# Per-intent cost, latency, cache hit rate, egress class
curl -s localhost:9080/v1/routing/report
```

The routing report counts cache hits as zero cost. Hits replay the stored
`usage` numbers from the original completion, so summing `usage` across
responses would overcount spend and hide the saving the report exists to show.

## Production readiness

- **pgvector semantic cache.** Set `KUBEMIND_SEMANTIC_CACHE_BACKEND=pgvector`
  (Helm default). Redis list remains the laptop default.
- **Redis-backed circuit breakers.** Provider breakers share state across
  replicas; they fall back to in-process memory if Redis is down.
- **Helm chart.** `charts/kubemind/` replaces the retired `k8s/switchboard*`
  manifests. `make helm-template` renders without installing.
- **Cascade.** Opt-in via `routing.cascade.enabled`. Never escalates past a
  `local_only` verdict. `make demo` exercises the partner story end to end.
- **Linear head.** `make eval-train-linear` trains offline and refuses to write
  a model that does not beat k-NN on consequence-weighted error.
- **Calibration.** `make eval-calibrate` fits the softmax temperature on a
  held-out split.

## Known limits

- Intent classification is single-label. A prompt spanning several intents gets
  the dominant one; sensitivity is evaluated independently, so this does not
  weaken enforcement.
- The linear head needs more labelled traffic than the 54-example eval set
  before it reliably beats k-NN — that is intentional.
