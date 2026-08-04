"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { agentsApi } from "@/lib/api";
import { Bot, Play, Loader2, Sparkles, Terminal, CheckCircle2, AlertTriangle } from "lucide-react";

export default function AgentsPage() {
  const [missions, setMissions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);

  async function loadMissions() {
    try {
      const data = await agentsApi.missions(20);
      setMissions(Array.isArray(data) ? data : []);
    } catch {
      setMissions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMissions();
    const interval = setInterval(loadMissions, 5000);
    return () => clearInterval(interval);
  }, []);

  async function runMission(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim() || running) return;
    setRunning(true);
    try {
      await agentsApi.createMission(prompt, "sync");
      setPrompt("");
      await loadMissions();
    } catch (err: any) {
      alert("Failed: " + err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-8 rounded-3xl bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Bot className="w-3.5 h-3.5" />
            <span>Autonomous Task Planner</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Agent Missions Console</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Dispatch multi-step prompts to KubeMind's autonomous agents. Armed with 7 sandboxed execution tools.
          </p>
        </div>
      </div>

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
              placeholder="e.g. Analyze repository files and build unit test suite for user service..."
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
                  <span>Planning...</span>
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

      {/* Mission History */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <span>Mission History & Traces</span>
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

        {missions.map((m) => (
          <Card key={m.id} className="p-6 bg-[#0F172A] border border-[#1E293B] space-y-4">
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
        ))}
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
