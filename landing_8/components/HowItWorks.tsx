"use client";

import { motion } from "framer-motion";

const steps = [
  {
    n: "01",
    title: "Purpose",
    body: "kmind reads the latest turn (with weighted history) and assigns a purpose — code, retrieve, security, ops, or general — before any provider is chosen.",
  },
  {
    n: "02",
    title: "Intent",
    body: "Rules plus k-NN over your examples pick a route profile: model pool, params, cache policy, and whether mind should retrieve context.",
  },
  {
    n: "03",
    title: "Route",
    body: "Sensitivity overlays the pool — redact, local-only, or block. Then kmind dispatches, cascades if needed, or refuses with a ledger entry.",
  },
  {
    n: "04",
    title: "Prove",
    body: "Every decision — intent, confidence, egress class, target — lands in a hash-chained audit ledger you can verify.",
  },
];

export default function HowItWorks() {
  return (
    <section id="kmind" className="border-t border-line bg-ink-soft py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-8">
        <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-signal">
          kmind · the router
        </p>
        <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-paper md:text-4xl">
          Purpose in. Intent found. Route out.
        </h2>
        <p className="mt-4 max-w-2xl text-fog">
          <span className="text-paper">KubeMind</span> is the control plane.
          The router is{" "}
          <span className="font-[family-name:var(--font-mono)] text-signal">kmind</span>
          — not a dumb forwarder. Purpose picks the cheapest capable target;
          sensitivity decides which targets are even eligible.{" "}
          <a href="/kmind" className="text-paper underline decoration-line underline-offset-4 transition hover:decoration-signal">
            Full kmind page →
          </a>
        </p>

        <ol className="mt-16 grid gap-10 md:grid-cols-2">
          {steps.map((s, i) => (
            <motion.li
              key={s.n}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.55, delay: i * 0.08 }}
              className="border-t border-line pt-6"
            >
              <span className="font-[family-name:var(--font-mono)] text-sm text-signal">
                {s.n}
              </span>
              <h3 className="mt-2 font-[family-name:var(--font-display)] text-xl font-semibold text-paper">
                {s.title}
              </h3>
              <p className="mt-2 text-fog leading-relaxed">{s.body}</p>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
