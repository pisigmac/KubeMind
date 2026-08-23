"use client";

import { motion } from "framer-motion";

const demos = [
  {
    label: "kmind → code",
    prompt: "Write a Python function that parses YAML",
    result: "intent: code · profile pool prefers local deepseek / ollama",
    tone: "sea" as const,
  },
  {
    label: "kmind → retrieve",
    prompt: "What does our handbook say about expenses?",
    result: "intent: rag · mind query injected before dispatch",
    tone: "signal" as const,
  },
  {
    label: "kmind → block",
    prompt: "Deploy with -----BEGIN PRIVATE KEY-----",
    result: "policy block · HTTP 403 · never reaches a provider",
    tone: "danger" as const,
  },
  {
    label: "kmind → local_only",
    prompt: "Email alice@example.com the report",
    result: "cloud pool dropped · 503 if no local model",
    tone: "signal" as const,
  },
];

const toneClass = {
  sea: "text-sea",
  signal: "text-signal",
  danger: "text-danger",
};

export default function Proof() {
  return (
    <section id="proof" className="py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-8">
        <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-signal">
          Partner proof
        </p>
        <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight md:text-4xl">
          Four prompts. Four kmind decisions.
        </h2>
        <p className="mt-4 max-w-2xl text-fog">
          Same stack a design partner runs with{" "}
          <span className="font-[family-name:var(--font-mono)] text-paper">make demo</span>.
          Each outcome is verifiable in the audit ledger — not a slide.
        </p>

        <div className="mt-14 space-y-1 border border-line bg-panel/40">
          {demos.map((d, i) => (
            <motion.article
              key={d.label}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: i * 0.06 }}
              className="grid gap-3 border-b border-line px-5 py-6 last:border-b-0 md:grid-cols-[11rem_1fr_1.2fr] md:items-baseline md:gap-8"
            >
              <span
                className={`font-[family-name:var(--font-mono)] text-xs uppercase tracking-wider ${toneClass[d.tone]}`}
              >
                {d.label}
              </span>
              <p className="font-[family-name:var(--font-mono)] text-sm text-paper/90">
                {d.prompt}
              </p>
              <p className="text-sm text-fog">{d.result}</p>
            </motion.article>
          ))}
        </div>

        <p className="mt-6 font-[family-name:var(--font-mono)] text-sm text-fog">
          $ make demo
        </p>
      </div>
    </section>
  );
}
