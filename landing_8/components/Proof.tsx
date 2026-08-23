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
    result: "intent: rag · mind query injected before dispatch · fail-closed 503 if mind offline",
    tone: "signal" as const,
  },
  {
    label: "kmind → pseudonymize",
    prompt: "Dr. Jane Doe lives at 742 Evergreen Terrace and requested a summary",
    result: "offline NER replaces PII with tokens → cloud gets tokens → tokens restored on response",
    tone: "sea" as const,
  },
  {
    label: "kmind → block",
    prompt: "Deploy with -----BEGIN PRIVATE KEY-----",
    result: "policy block · HTTP 403 · never reaches any provider",
    tone: "danger" as const,
  },
  {
    label: "kmind → local_only",
    prompt: "Email alice@example.com the patient report",
    result: "cloud pool dropped · routed exclusively to local on-premise model",
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
          Deterministic Proof
        </p>
        <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight md:text-4xl">
          Five prompts. Five auditable kmind decisions.
        </h2>
        <p className="mt-4 max-w-2xl text-fog">
          Same stack you run with{" "}
          <span className="font-[family-name:var(--font-mono)] text-paper">make demo</span>.
          Every single outcome is recorded into an immutable SHA-256 hash-chained ledger.
        </p>

        <div className="mt-14 space-y-1 border border-line bg-panel/40">
          {demos.map((d, i) => (
            <motion.article
              key={d.label}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: i * 0.06 }}
              className="grid gap-3 border-b border-line px-5 py-6 last:border-b-0 md:grid-cols-[13rem_1fr_1.2fr] md:items-baseline md:gap-8"
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

        <div className="mt-6 flex items-center justify-between font-[family-name:var(--font-mono)] text-sm text-fog">
          <span>$ make demo</span>
          <span className="text-xs text-signal/80">API: /v1/route · /v1/chat/completions</span>
        </div>
      </div>
    </section>
  );
}
