"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { agentsApi } from "@/lib/api";
import {
  Bot,
  Play,
  Loader2,
  Terminal,
  AlertTriangle,
  GitBranch,
  Search,
  Wrench,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  Database,
  Cpu,
  Layers,
} from "lucide-react";

interface MissionNode {
  id: string;
  name: string;
  category: "intent" | "memory" | "planner" | "tools" | "sentinel" | "output";
  status: "idle" | "running" | "completed" | "failed";
  details: string;
}

export default function AgentsPage() {
  const [missions, setMissions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [selectedMission, setSelectedMission] = useState<any | null>(null);

  async function loadMissions() {
    try {
      const data = await agentsApi.missions(20);
      const list = Array.isArray(data) ? data : [];
      setMissions(list);
      if (list.length > 0 && !selectedMission) {
        setSelectedMission(list[0]);
      }
    } catch {
      setMissions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMissions();
    const interval = setInterval(loadMissions, 4000);
    return () => clearInterval(interval);
  }, []);

  async function runMission(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim() || running) return;
    setRunning(true);
    try {
      const created = await agentsApi.createMission(prompt, "sync");
      setPrompt("");
      await loadMissions();
      if (created) setSelectedMission(created);
    } catch (err: any) {
      alert("Failed: " + err.message);
    } finally {
      setRunning(false);
    }
  }

  // Generate dynamic DAG nodes based on active/selected mission state
  const dagNodes: MissionNode[] = [
    {
      id: "node-1",
      name: "1. Intent & Policy Gating",
      category: "intent",
      status: running ? "running" : selectedMission ? "completed" : "idle",
      details: "Classify semantic route & check offline NER redaction",
    },
    {
      id: "node-2",
      name: "2. Mind Graph Grounding",
      category: "memory",
      status: running ? "running" : selectedMission ? "completed" : "idle",
      details: "Retrieve hybrid vector + node context from pgvector",
    },
    {
      id: "node-3",
      name: "3. Multi-Step Planner",
      category: "planner",
      status: running ? "running" : selectedMission?.status === "completed" ? "completed" : selectedMission?.status === "failed" ? "failed" : "idle",
      details: "Decompose mission into tool execution plan",
    },
    {
      id: "node-4",
      name: "4. Sandboxed Tool Execution",
      category: "tools",
      status: running ? "running" : selectedMission?.status === "completed" ? "completed" : selectedMission?.status === "failed" ? "failed" : "idle",
      details: "Bash, file edit, ripgrep, web search sandbox",
    },
    {
      id: "node-5",
      name: "5. Sentinel Ledger Span",
      category: "sentinel",
      status: selectedMission ? "completed" : "idle",
      details: "Append SHA-256 tamper-evident span to audit ledger",
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-8 rounded-3xl bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Bot className="w-3.5 h-3.5" />
            <span>Autonomous Task Planner & Tool Runtime</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Agent Missions & DAG Pipeline</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Dispatch multi-step autonomous missions with interactive execution graph tracing, sandboxed tool loops, and SHA-256 audit spans.
          </p>
        </div>
      </div>

      {/* DAG Mission Flowchart Visualizer */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-bold text-base">
            <Layers className="w-5 h-5 text-[#0066FF]" />
            <span>Active Mission Execution DAG</span>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-[#1E293B] px-2.5 py-1 rounded-full">
            {running ? "Execution in Progress" : selectedMission ? `Selected ID: ${selectedMission.id?.slice(0, 8)}` : "Ready"}
          </span>
        </div>

        {/* Visual Workflow Graph */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 pt-2">
          {dagNodes.map((node, idx) => (
            <div key={node.id} className="relative flex flex-col">
              <div
                className={`p-4 rounded-2xl border transition-all h-full flex flex-col justify-between ${
                  node.status === "running"
                    ? "bg-[#0066FF]/10 border-[#0066FF] shadow-lg shadow-[#0066FF]/20 animate-pulse"
                    : node.status === "completed"
                    ? "bg-[#090D16] border-emerald-500/30"
                    : node.status === "failed"
                    ? "bg-rose-500/10 border-rose-500/40"
                    : "bg-[#090D16] border-[#1E293B] opacity-60"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-mono font-bold text-slate-400">
                      Step {idx + 1}
                    </span>
                    {node.status === "running" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0066FF]" />
                    ) : node.status === "completed" ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : node.status === "failed" ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-slate-700" />
                    )}
                  </div>
                  <h3 className="text-xs font-bold text-white mb-1">{node.name}</h3>
                  <p className="text-[11px] text-slate-400 leading-snug">{node.details}</p>
                </div>
              </div>

              {idx < dagNodes.length - 1 && (
                <div className="hidden md:flex absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-600">
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Dispatch Prompt Input Form */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl">
        <form onSubmit={runMission} className="space-y-4">
          <div className="flex items-center justify-between font-mono text-xs text-slate-400">
            <span className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#0066FF]" />
              New Autonomous Mission Prompt
            </span>
            <span className="text-[#0066FF] font-bold">Sync & Async Queue Ready</span>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Ingest repo documentation and build comprehensive security regression suite..."
              className="flex-1 px-4 py-3 border border-[#1E293B] rounded-xl bg-[#090D16] text-white text-sm focus:outline-none focus:border-[#0066FF] transition-all font-sans"
            />
            <button
              type="submit"
              className="btn-primary flex items-center gap-2 shrink-0"
              disabled={running}
            >
              {running ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Executing Plan...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Dispatch Mission</span>
                </>
              )}
            </button>
          </div>
        </form>
      </Card>

      {/* Mission History & Detail Traces */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <span>Mission Logs & Tracing</span>
          <span className="text-xs font-mono font-normal text-slate-400 bg-[#1E293B] px-2.5 py-0.5 rounded-full">
            {missions.length} Missions Logged
          </span>
        </h2>

        {loading && (
          <Card className="p-8 text-center bg-[#0F172A] border border-[#1E293B]">
            <Loader2 className="w-6 h-6 animate-spin text-[#0066FF] mx-auto mb-2" />
            <p className="text-xs text-slate-400 font-mono">Loading active mission queue...</p>
          </Card>
        )}

        {!loading && missions.length === 0 && (
          <Card className="p-12 text-center bg-[#0F172A] border border-[#1E293B]">
            <Bot className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-300 font-bold text-base">No agent missions logged yet</p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Enter a mission prompt in the dispatch bar above to trigger autonomous task execution.
            </p>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4">
          {missions.map((m) => {
            const isSelected = selectedMission?.id === m.id;
            return (
              <Card
                key={m.id}
                onClick={() => setSelectedMission(m)}
                className={`p-6 bg-[#0F172A] border transition-all cursor-pointer space-y-4 ${
                  isSelected ? "border-[#0066FF] shadow-lg shadow-[#0066FF]/10" : "border-[#1E293B] hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-[#0066FF] bg-[#0066FF]/10 px-2.5 py-1 rounded-lg border border-[#0066FF]/30">
                      ID: {m.id?.slice(0, 8)}
                    </span>
                    <StatusPill status={m.status} />
                  </div>
                  <span className="text-xs font-mono text-slate-500">Workspace: default</span>
                </div>

                <p className="text-sm font-semibold text-white leading-relaxed">{m.prompt}</p>

                {m.output && (
                  <div className="p-4 bg-[#090D16] border border-[#1E293B] rounded-xl font-mono text-xs text-slate-300 overflow-auto max-h-48">
                    <div className="text-slate-500 font-bold mb-1.5 flex items-center gap-1.5">
                      <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Execution Output Trace:</span>
                    </div>
                    <pre className="whitespace-pre-wrap">{m.output}</pre>
                  </div>
                )}

                {m.error && (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl font-mono text-xs text-rose-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{m.error}</span>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30",
    failed: "bg-rose-500/10 text-rose-400 border border-rose-500/30",
    running: "bg-blue-500/10 text-blue-400 border border-blue-500/30",
    queued: "bg-slate-800 text-slate-400 border border-slate-700",
    cancelled: "bg-amber-500/10 text-amber-400 border border-amber-500/30",
  };
  return (
    <span className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full ${colors[status] || colors.queued}`}>
      {status}
    </span>
  );
}
