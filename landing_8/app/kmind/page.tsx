import type { Metadata } from "next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import ComponentShell from "@/components/ComponentShell";

export const metadata: Metadata = {
  title: "kmind — intent router | KubeMind",
  description:
    "kmind gives your prompt a purpose, finds the intent, and routes it — with sensitivity enforced before any model call.",
};

export default function KmindPage() {
  return (
    <>
      <Nav />
      <ComponentShell
        name="kmind"
        port="9080"
        role="Intent-aware LLM gateway"
        headline="Gives your prompt a purpose, finds the intent, and routes it."
        lede="The only path for model calls in KubeMind. Classify once for purpose and sensitivity, pick a route profile, optionally retrieve from mind, then dispatch — or refuse — with a ledger entry."
        features={[
          {
            title: "Purpose & intent",
            body: "Rules prior plus k-NN over your examples. Margin confidence, abstain to general, background decoy for OOD traffic.",
          },
          {
            title: "Sensitivity overlay",
            body: "PII, secrets, and injection run inline — independent of intent. Redact, local-only, or block before a provider sees the prompt.",
          },
          {
            title: "Profiles & cache",
            body: "Pool, model, params, and retrieval from config. Exact cache first; semantic cache is model-aware and intent-partitioned.",
          },
          {
            title: "Decision record",
            body: "Every request leaves intent, confidence, egress class, and target for sentinel’s hash-chained ledger.",
          },
        ]}
        endpoints={[
          "POST /v1/chat/completions",
          "POST /v1/route",
          "POST /v1/classify",
          "POST /v1/embeddings",
          "GET  /v1/routing/report",
          "GET  /metrics",
        ]}
        next={{ href: "/mind", label: "mind" }}
      />
      <Footer />
    </>
  );
}
