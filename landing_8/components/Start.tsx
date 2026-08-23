"use client";

import { motion } from "framer-motion";

export default function Start() {
  return (
    <section id="start" className="border-t border-line py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.55 }}
        >
          <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-signal">
            Get started
          </p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight md:text-4xl">
            Bring up KubeMind. Hit kmind tonight.
          </h2>
          <pre className="mt-10 overflow-x-auto border border-line bg-panel/50 p-6 font-[family-name:var(--font-mono)] text-sm leading-relaxed text-sea md:p-8">
{`cp .env.example .env
make up          # control plane + kmind on :9080
make demo        # four intent / policy prompts

# OpenAI-compatible
curl -s localhost:9080/v1/chat/completions \\
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \\
  -d '{"model":"auto","messages":[{"role":"user","content":"..."}]}'

# Or the kmind CLI
kmind status`}
          </pre>
          <p className="mt-8 max-w-xl text-fog leading-relaxed">
            Deep dives:{" "}
            <span className="text-paper">docs/architecture.md</span>,{" "}
            <span className="text-paper">docs/design/intent-routing.md</span>,
            Helm at <span className="text-paper">charts/kubemind/</span>.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <a
              href="#kmind"
              className="rounded-sm border border-line px-5 py-2.5 text-sm text-paper transition hover:border-fog"
            >
              How kmind works
            </a>
            <a
              href="#proof"
              className="rounded-sm border border-line px-5 py-2.5 text-sm text-paper transition hover:border-fog"
            >
              Partner proof
            </a>
            <a
              href="#vs"
              className="rounded-sm bg-signal px-5 py-2.5 text-sm font-semibold text-ink transition hover:bg-signal-hot"
            >
              Why KubeMind
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
