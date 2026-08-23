import type { Metadata } from "next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import ComponentShell from "@/components/ComponentShell";

export const metadata: Metadata = {
  title: "agents — missions | KubeMind",
  description:
    "agents run multi-step missions with tools. Every LLM call still goes through kmind.",
};

export default function AgentsPage() {
  return (
    <>
      <Nav />
      <ComponentShell
        name="agents"
        port="9082"
        role="Mission planner & tools"
        headline="Long-running work — still under kmind governance."
        lede="agents plan and execute missions with filesystem, shell, web, and knowledge tools. They never bypass the gateway: every model call is purpose-classified and sensitivity-checked by kmind."
        features={[
          {
            title: "Missions",
            body: "Create sync or async missions. Planner loop breaks work into tool steps and persists state.",
          },
          {
            title: "Tools",
            body: "fs, shell, web, and knowledge connectors today. Kubernetes-aware tools are on the roadmap with HITL for mutations.",
          },
          {
            title: "kmind-bound",
            body: "No shadow OpenAI clients. Provider choice, cache, and policy stay on the single decision path.",
          },
          {
            title: "Workspace keys",
            body: "Same API-key tenancy as the rest of the plane — missions inherit the caller’s workspace.",
          },
        ]}
        endpoints={[
          "POST /v1/missions",
          "GET  /v1/missions/{id}",
          "GET  /v1/tools",
          "POST /v1/tools/invoke",
        ]}
        prev={{ href: "/mind", label: "mind" }}
        next={{ href: "/sentinel", label: "sentinel" }}
      />
      <Footer />
    </>
  );
}
