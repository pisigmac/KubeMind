"use client";

import { motion } from "framer-motion";
import HeroMesh from "./HeroMesh";

export default function Hero() {
  return (
    <section
      id="top"
      className="relative flex min-h-[100svh] flex-col justify-end overflow-hidden pb-16 pt-28 md:pb-24 md:pt-32"
    >
      <HeroMesh />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 md:px-8">
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="font-[family-name:var(--font-display)] text-5xl font-semibold tracking-tight text-paper sm:text-6xl md:text-7xl lg:text-8xl"
        >
          KubeMind
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
          className="mt-5 max-w-3xl font-[family-name:var(--font-display)] text-2xl font-medium leading-snug tracking-tight text-paper/95 sm:text-3xl md:text-4xl"
        >
          <span className="font-[family-name:var(--font-mono)] text-signal">kmind</span>{" "}
          gives your prompt a purpose, finds the intent, and routes it.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="mt-5 max-w-xl text-base leading-relaxed text-fog md:text-lg"
        >
          The router at the heart of KubeMind. Classify once — for purpose and
          sensitivity — then retrieve, redact, force local, or block before any
          model is called.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.32, ease: [0.22, 1, 0.36, 1] }}
          className="mt-9 flex flex-wrap items-center gap-4"
        >
          <a
            href="#start"
            className="rounded-sm bg-signal px-6 py-3 text-sm font-semibold text-ink transition hover:bg-signal-hot"
          >
            Run kmind
          </a>
          <a
            href="#kmind"
            className="rounded-sm border border-line px-6 py-3 text-sm font-medium text-paper transition hover:border-fog hover:bg-panel/40"
          >
            How kmind works
          </a>
        </motion.div>
      </div>
    </section>
  );
}
