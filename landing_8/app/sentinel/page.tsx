import type { Metadata } from "next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import ComponentShell from "@/components/ComponentShell";

export const metadata: Metadata = {
  title: "sentinel — proof & observability | KubeMind",
  description:
    "sentinel stores spans, scrapes metrics, and anchors kmind decisions in a hash-chained audit ledger.",
};

export default function SentinelPage() {
  return (
    <>
      <Nav />
      <ComponentShell
        name="sentinel"
        port="9083"
        role="Observability & audit ledger"
        headline="See the call. Prove the decision."
        lede="sentinel ingests spans, redacts secrets, scores injection heuristics, and exposes Prometheus. Decision records from kmind append to a hash-chained ledger you can verify — the wedge against mutable logs."
        features={[
          {
            title: "Audit ledger",
            body: "Hash-chained per workspace. Verify, head, entries, and retention/legal hold endpoints for partner proof.",
          },
          {
            title: "Shared detectors",
            body: "Redaction and guardrails from kubemind_policy — same package kmind uses inline, so ingest cannot drift.",
          },
          {
            title: "Live stream",
            body: "WebSocket span stream for the operator dashboard. Metrics on /metrics for Prometheus scrapes.",
          },
          {
            title: "Export",
            body: "Ordered export with redaction metadata for offline review — optional checksum manifest.",
          },
        ]}
        endpoints={[
          "POST /v1/spans",
          "GET  /v1/spans",
          "GET  /v1/telemetry/traces",
          "GET  /v1/audit/verify",
          "GET  /v1/audit/head",
          "WS   /v1/stream",
          "GET  /metrics",
        ]}
        prev={{ href: "/agents", label: "agents" }}
        next={{ href: "/kmind", label: "kmind" }}
      />
      <Footer />
    </>
  );
}
