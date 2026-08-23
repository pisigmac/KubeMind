"use client";

import { motion } from "framer-motion";

const rows = [
  {
    them: "LiteLLM / Portkey route by static model names",
    us: "kmind routes by classified intent → dynamic fallback profile",
  },
  {
    them: "Helicone / Langfuse observe PII after external dispatch",
    us: "kmind enforces pre-dispatch sensitivity gating & local-first fallback",
  },
  {
    them: "Destructive regex redaction breaks LLM context",
    us: "In-memory reversible pseudonymization (NER token mapping restored on return)",
  },
  {
    them: "Silent hallucination when internal memory is down",
    us: "Fail-closed 503 & explicit empty grounding labelling (No fake context)",
  },
  {
    them: "No owned knowledge plane",
    us: "Retrieval intents assemble context from native mind pgvector graph",
  },
  {
    them: "Mutable SQL logs vulnerable to tampering",
    us: "Immutable SHA-256 hash-chained ledger with /v1/audit/verify endpoint",
  },
];

export default function Versus() {
  return (
    <section id="vs" className="border-t border-line bg-paper py-24 text-ink md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-8">
        <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-ink/50">
          The competitive wedge
        </p>
        <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight md:text-4xl">
          Others forward.{" "}
          <span className="font-[family-name:var(--font-mono)] text-[0.92em]">kmind</span>{" "}
          governs.
        </h2>

        <div className="mt-14 divide-y divide-ink/10 border-y border-ink/10">
          {rows.map((r, i) => (
            <motion.div
              key={r.us}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: i * 0.05 }}
              className="grid gap-4 py-7 md:grid-cols-2 md:gap-12"
            >
              <p className="text-ink/45">{r.them}</p>
              <p className="font-medium text-ink">{r.us}</p>
            </motion.div>
          ))}
        </div>

        <p className="mt-10 max-w-2xl text-ink/70 leading-relaxed">
          Governance never depends on the intent classifier. Wrong intent costs
          quality. Missed sensitivity is an incident. Those are different
          problems — KubeMind keeps them apart on purpose, inside{" "}
          <span className="font-[family-name:var(--font-mono)] text-ink">kmind</span>.
        </p>
      </div>
    </section>
  );
}
