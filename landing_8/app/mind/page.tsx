import type { Metadata } from "next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import ComponentShell from "@/components/ComponentShell";

export const metadata: Metadata = {
  title: "mind — knowledge plane | KubeMind",
  description:
    "mind holds workspace knowledge. Hybrid search and graph retrieval when kmind classifies a retrieve intent.",
};

export default function MindPage() {
  return (
    <>
      <Nav />
      <ComponentShell
        name="mind"
        port="9081"
        role="Knowledge graph & hybrid search"
        headline="Your workspace memory — retrieved when intent says so."
        lede="mind ingests docs, repos, and web sources into vectors, keywords, and a graph. kmind calls it only for retrieval intents, so every RAG path still passes purpose and sensitivity first."
        features={[
          {
            title: "Hybrid query",
            body: "Vector + keyword + graph in one query path. Workspace-scoped so tenants never see each other’s nodes.",
          },
          {
            title: "Ingest connectors",
            body: "Documents, git, and web sources land as chunked, embeddable knowledge with configurable chunking.",
          },
          {
            title: "pgvector first-class",
            body: "HNSW in the default compose image. Same Postgres the rest of the plane trusts.",
          },
          {
            title: "Called by kmind",
            body: "Retrieval is a route-profile flag — not a separate unmanaged sidecar. Governance still applies.",
          },
        ]}
        endpoints={[
          "POST /v1/ingest",
          "POST /v1/query",
          "POST /v1/memory/query",
          "GET  /v1/graph",
        ]}
        prev={{ href: "/kmind", label: "kmind" }}
        next={{ href: "/agents", label: "agents" }}
      />
      <Footer />
    </>
  );
}
