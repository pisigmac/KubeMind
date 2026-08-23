"use client";

import Link from "next/link";
import { motion } from "framer-motion";

const parts = [
  {
    href: "/kmind",
    name: "kmind",
    port: "9080",
    line: "Purpose → intent → route. The only path for LLM calls.",
  },
  {
    href: "/mind",
    name: "mind",
    port: "9081",
    line: "Workspace knowledge. Hybrid search when intent is retrieve.",
  },
  {
    href: "/agents",
    name: "agents",
    port: "9082",
    line: "Missions and tools. All model traffic still through kmind.",
  },
  {
    href: "/sentinel",
    name: "sentinel",
    port: "9083",
    line: "Spans, metrics, and the hash-chained audit ledger.",
  },
];

export default function Plane() {
  return (
    <section id="plane" className="border-t border-line py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-8">
        <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-signal">
          Control plane
        </p>
        <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight md:text-4xl">
          Four services. One decision path.
        </h2>
        <p className="mt-4 max-w-2xl text-fog">
          KubeMind is the product. Each component has a job — open a page for
          the details.
        </p>

        <ul className="mt-14 divide-y divide-line border-y border-line">
          {parts.map((p, i) => (
            <motion.li
              key={p.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: i * 0.05 }}
            >
              <Link
                href={p.href}
                className="group grid gap-2 py-7 transition md:grid-cols-[8rem_4rem_1fr] md:items-baseline md:gap-8"
              >
                <span className="font-[family-name:var(--font-mono)] text-signal group-hover:text-signal-hot">
                  {p.name}
                </span>
                <span className="font-[family-name:var(--font-mono)] text-xs text-fog">
                  :{p.port}
                </span>
                <span className="text-fog group-hover:text-paper">{p.line}</span>
              </Link>
            </motion.li>
          ))}
        </ul>
      </div>
    </section>
  );
}
