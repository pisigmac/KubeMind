"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Zap, Cpu, Network, Activity, ShieldCheck, Terminal, 
  ArrowRight, CheckCircle2, ChevronRight, Layers, Sparkles,
  Command, Code2, Database, BarChart3, Bot, Compass, RefreshCw
} from "lucide-react";

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState<"agents" | "knowledge" | "gateway" | "observability">("agents");
  const [terminalStep, setTerminalStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setTerminalStep((prev) => (prev + 1) % 4);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#080B11] text-slate-100 font-sans selection:bg-cyan-500 selection:text-black overflow-x-hidden">
      {/* Background Glow Elements */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[20%] w-[600px] h-[600px] bg-cyan-600/10 rounded-full blur-[140px]" />
        <div className="absolute top-[40%] right-[-5%] w-[500px] h-[500px] bg-indigo-600/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-10%] left-[10%] w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[140px]" />
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:32px_32px] opacity-20" />
      </div>

      {/* Top Navbar */}
      <header className="relative z-50 border-b border-slate-800/80 backdrop-blur-xl bg-[#080B11]/70 sticky top-0">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-emerald-400 p-[1px] shadow-lg shadow-cyan-500/20">
              <div className="w-full h-full bg-[#0B0F19] rounded-[11px] flex items-center justify-center">
                <Cpu className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <span className="text-xl font-black tracking-wider text-white font-mono">KUBEMIND</span>
              <span className="ml-2 text-[10px] uppercase font-bold tracking-widest text-cyan-400 bg-cyan-950/80 border border-cyan-800/50 px-2 py-0.5 rounded-full">v0.1.0</span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-400 font-medium">
            <a href="#features" className="hover:text-cyan-400 transition-colors">Stack Architecture</a>
            <a href="#interactive" className="hover:text-cyan-400 transition-colors">Interactive Engine</a>
            <a href="#benchmark" className="hover:text-cyan-400 transition-colors">Benchmarks</a>
            <a href="#docs" className="hover:text-cyan-400 transition-colors">Docs</a>
          </nav>

          <div className="flex items-center gap-4">
            <Link 
              href="/app" 
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-sm shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-2 group"
            >
              <span>Launch Platform</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-20 pb-28 max-w-7xl mx-auto px-6 text-center">
        {/* Pill Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-slate-300 text-xs font-mono mb-8 shadow-inner">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span>Distributed Autonomous Agent Runtime</span>
          <span className="text-slate-600">|</span>
          <span className="text-cyan-400 font-semibold">Zero SaaS Vendor Lock</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-extrabold tracking-tight text-white max-w-5xl mx-auto leading-[1.08] mb-8">
          The Self-Hosted <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-cyan-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
            AI Infrastructure Core
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-lg md:text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed mb-12 font-normal">
          Orchestrate multi-step LLM routing, hybrid knowledge graph memory, autonomous tool execution, and real-time telemetry — unified in a single, resilient microservice stack.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-20">
          <Link
            href="/app"
            className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 text-white font-bold text-base shadow-xl shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-3"
          >
            <Zap className="w-5 h-5 fill-current text-cyan-200" />
            <span>Open Developer Console</span>
          </Link>

          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="w-full sm:w-auto px-8 py-4 rounded-xl bg-slate-900/80 border border-slate-700/80 text-slate-200 font-bold text-base hover:bg-slate-800 hover:border-slate-600 transition-all flex items-center justify-center gap-3 font-mono"
          >
            <Terminal className="w-5 h-5 text-cyan-400" />
            <span>make up</span>
          </a>
        </div>

        {/* Hero Interactive Terminal Graphic */}
        <div className="relative max-w-5xl mx-auto rounded-2xl border border-slate-800 bg-[#0B0F19]/90 shadow-2xl shadow-cyan-500/10 overflow-hidden backdrop-blur-2xl">
          {/* Terminal Topbar */}
          <div className="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800/80 flex items-center justify-between font-mono text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-rose-500/80" />
              <div className="w-3 h-3 rounded-full bg-amber-500/80" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="ml-3 text-slate-500">tricore-runtime ~ bash</span>
            </div>
            <div className="flex items-center gap-4 text-[11px]">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                STACK ONLINE
              </span>
              <span className="text-slate-500">PORTS: 9080-9083</span>
            </div>
          </div>

          {/* Terminal Body */}
          <div className="p-6 md:p-8 font-mono text-left text-sm text-slate-300 space-y-4">
            <div className="flex items-center gap-3 text-slate-500 border-b border-slate-800/60 pb-3">
              <span className="text-cyan-400">$</span>
              <span>docker compose up --build -d</span>
              <span className="ml-auto text-xs text-slate-600">Time: 1.2s</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
              <div className={`p-4 rounded-xl border transition-all ${terminalStep === 0 ? 'bg-cyan-950/30 border-cyan-500/50 shadow-lg shadow-cyan-500/10' : 'bg-slate-900/40 border-slate-800/80'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">ROUTER :9080</span>
                  <Activity className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="text-xs text-slate-400">Model Load Balance</div>
                <div className="text-sm font-semibold text-white mt-1">Ollama / Llama3.1</div>
              </div>

              <div className={`p-4 rounded-xl border transition-all ${terminalStep === 1 ? 'bg-indigo-950/30 border-indigo-500/50 shadow-lg shadow-indigo-500/10' : 'bg-slate-900/40 border-slate-800/80'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">MIND :9081</span>
                  <Database className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="text-xs text-slate-400">Hybrid Graph Index</div>
                <div className="text-sm font-semibold text-white mt-1">Vector + Keyword</div>
              </div>

              <div className={`p-4 rounded-xl border transition-all ${terminalStep === 2 ? 'bg-emerald-950/30 border-emerald-500/50 shadow-lg shadow-emerald-500/10' : 'bg-slate-900/40 border-slate-800/80'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">AGENTS :9082</span>
                  <Bot className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-xs text-slate-400">Autonomous Planner</div>
                <div className="text-sm font-semibold text-white mt-1">7 Tools Armed</div>
              </div>

              <div className={`p-4 rounded-xl border transition-all ${terminalStep === 3 ? 'bg-amber-950/30 border-amber-500/50 shadow-lg shadow-amber-500/10' : 'bg-slate-900/40 border-slate-800/80'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">SENTINEL :9083</span>
                  <BarChart3 className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-xs text-slate-400">Telemetry Ingestion</div>
                <div className="text-sm font-semibold text-white mt-1">WebSocket Stream</div>
              </div>
            </div>

            {/* Simulated Live Output Stream */}
            <div className="mt-4 p-4 rounded-xl bg-slate-950/90 border border-slate-800/80 font-mono text-xs text-slate-400 space-y-1.5">
              <div className="text-emerald-400 flex items-center gap-2">
                <span>✔</span> <span>[router] Health check OK — Connected to Ollama (llama3.1)</span>
              </div>
              <div className="text-cyan-400 flex items-center gap-2">
                <span>✔</span> <span>[mind] Knowledge Store initialized with PostgreSQL + vector embeddings</span>
              </div>
              <div className="text-indigo-400 flex items-center gap-2">
                <span>✔</span> <span>[agents] AgentEngine online — Loaded tools: [filesystem, shell, web_search, knowledge, ...]</span>
              </div>
              <div className="text-amber-400 flex items-center gap-2">
                <span>✔</span> <span>[sentinel] Telemetry daemon listening on ws://localhost:9083/v1/stream</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid Section */}
      <section id="features" className="relative z-10 py-24 border-t border-slate-800/60 bg-[#06090F]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto mb-20">
            <h2 className="text-xs uppercase font-bold tracking-widest text-cyan-400 mb-3 font-mono">Microservice Architecture</h2>
            <h3 className="text-4xl md:text-5xl font-black text-white tracking-tight">
              4 Specialized Engines. <br />
              One Cohesive Platform.
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Card 1: Router */}
            <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800/80 hover:border-cyan-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-cyan-950 border border-cyan-800/50 flex items-center justify-center text-cyan-400 mb-6 group-hover:scale-110 transition-transform">
                <Network className="w-6 h-6" />
              </div>
              <h4 className="text-2xl font-bold text-white mb-3">Router</h4>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Intelligent LLM gateway featuring automatic fallback, model load balancing, Redis response caching, and custom circuit breakers for 99.99% uptime.
              </p>
              <ul className="space-y-2.5 font-mono text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-cyan-400" /> Multi-provider failover routing</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-cyan-400" /> Redis response caching (&lt;10ms)</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-cyan-400" /> Granular rate limiting & token budgeting</li>
              </ul>
            </div>

            {/* Card 2: Mind */}
            <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800/80 hover:border-indigo-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-indigo-950 border border-indigo-800/50 flex items-center justify-center text-indigo-400 mb-6 group-hover:scale-110 transition-transform">
                <Database className="w-6 h-6" />
              </div>
              <h4 className="text-2xl font-bold text-white mb-3">Mind (ContextWeave)</h4>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Hybrid Knowledge Graph combining vector semantic embeddings with exact keyword matching. Ingest code repositories, markdown docs, or PDFs seamlessly.
              </p>
              <ul className="space-y-2.5 font-mono text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-400" /> Hybrid Vector + BM25 keyword search</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-400" /> Code, doc, and conversation connectors</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-indigo-400" /> Dynamic graph export & visualization</li>
              </ul>
            </div>

            {/* Card 3: Agents */}
            <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800/80 hover:border-emerald-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-emerald-950 border border-emerald-800/50 flex items-center justify-center text-emerald-400 mb-6 group-hover:scale-110 transition-transform">
                <Bot className="w-6 h-6" />
              </div>
              <h4 className="text-2xl font-bold text-white mb-3">Agents (DeepAgents)</h4>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Autonomous agent execution engine. Generates multi-step mission plans, executes shell commands, invokes code analyzers, and updates memory automatically.
              </p>
              <ul className="space-y-2.5 font-mono text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400" /> 7 pre-built execution tools armed</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400" /> Multi-step task planner & memory manager</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400" /> Async mission queue with cancellation</li>
              </ul>
            </div>

            {/* Card 4: Sentinel */}
            <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800/80 hover:border-amber-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-amber-950 border border-amber-800/50 flex items-center justify-center text-amber-400 mb-6 group-hover:scale-110 transition-transform">
                <BarChart3 className="w-6 h-6" />
              </div>
              <h4 className="text-2xl font-bold text-white mb-3">Sentinel (Tracer)</h4>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Distributed telemetry daemon collecting trace spans across all microservices. Streams real-time span events directly to the dashboard via WebSocket.
              </p>
              <ul className="space-y-2.5 font-mono text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-amber-400" /> Low-latency span ingestion engine</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-amber-400" /> WebSocket live trace streaming</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-amber-400" /> Service-level error rate & latency metrics</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Stack Explorer */}
      <section id="interactive" className="relative z-10 py-24 max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-xs uppercase font-bold tracking-widest text-cyan-400 mb-3 font-mono">Interactive Explorer</h2>
          <h3 className="text-4xl font-black text-white">Experience the Microservices</h3>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#0B0F19] overflow-hidden shadow-2xl">
          {/* Tab Selection Bar */}
          <div className="flex border-b border-slate-800/80 overflow-x-auto">
            <button
              onClick={() => setActiveTab("agents")}
              className={`flex-1 min-w-[140px] px-6 py-4 font-mono text-xs font-bold transition-all flex items-center justify-center gap-2 ${activeTab === "agents" ? "bg-cyan-950/40 text-cyan-400 border-b-2 border-cyan-400" : "text-slate-400 hover:text-white"}`}
            >
              <Bot className="w-4 h-4" />
              <span>AGENTS ENGINE</span>
            </button>

            <button
              onClick={() => setActiveTab("knowledge")}
              className={`flex-1 min-w-[140px] px-6 py-4 font-mono text-xs font-bold transition-all flex items-center justify-center gap-2 ${activeTab === "knowledge" ? "bg-indigo-950/40 text-indigo-400 border-b-2 border-indigo-400" : "text-slate-400 hover:text-white"}`}
            >
              <Database className="w-4 h-4" />
              <span>KNOWLEDGE GRAPH</span>
            </button>

            <button
              onClick={() => setActiveTab("gateway")}
              className={`flex-1 min-w-[140px] px-6 py-4 font-mono text-xs font-bold transition-all flex items-center justify-center gap-2 ${activeTab === "gateway" ? "bg-emerald-950/40 text-emerald-400 border-b-2 border-emerald-400" : "text-slate-400 hover:text-white"}`}
            >
              <Network className="w-4 h-4" />
              <span>LLM GATEWAY</span>
            </button>

            <button
              onClick={() => setActiveTab("observability")}
              className={`flex-1 min-w-[140px] px-6 py-4 font-mono text-xs font-bold transition-all flex items-center justify-center gap-2 ${activeTab === "observability" ? "bg-amber-950/40 text-amber-400 border-b-2 border-amber-400" : "text-slate-400 hover:text-white"}`}
            >
              <Activity className="w-4 h-4" />
              <span>OBSERVABILITY</span>
            </button>
          </div>

          {/* Interactive Content Window */}
          <div className="p-8">
            {activeTab === "agents" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-mono text-cyan-400 font-semibold">POST /v1/missions (sync)</span>
                  <span className="text-xs text-slate-500 font-mono">Response: 142ms</span>
                </div>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-2">
                  <div className="text-slate-500">{"// Agent Mission Prompt: Analyze repo structure and create test suit"}</div>
                  <div className="text-cyan-400">{"Step 1: Invoking 'filesystem' tool -> listing workspace files"}</div>
                  <div className="text-indigo-400">{"Step 2: Invoking 'knowledge' tool -> querying vector store for Dockerfile specifications"}</div>
                  <div className="text-emerald-400">{"Step 3: Invoking 'write_file' tool -> created test.md with 6 verification phases"}</div>
                  <div className="text-emerald-300 font-bold pt-2">Status: COMPLETED (3 tool calls executed, 0 errors)</div>
                </div>
              </div>
            )}

            {activeTab === "knowledge" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-mono text-indigo-400 font-semibold">POST /v1/query (hybrid search)</span>
                  <span className="text-xs text-slate-500 font-mono">Embedding Model: nomic-embed-text</span>
                </div>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-2">
                  <div className="text-slate-500">{"// Query: 'FastAPI lifespan and sentinel tracer'"}</div>
                  <div className="flex justify-between items-center bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span>Node #1: router/main.py</span>
                    <span className="text-indigo-400">Score: 0.942 (Vector: 0.91, Keyword: 0.98)</span>
                  </div>
                  <div className="flex justify-between items-center bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span>Node #2: mind/tracer.py</span>
                    <span className="text-indigo-400">Score: 0.887 (Vector: 0.85, Keyword: 0.92)</span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "gateway" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-mono text-emerald-400 font-semibold">POST /v1/chat/completions</span>
                  <span className="text-xs text-slate-500 font-mono">Policy: Cost-Optimized</span>
                </div>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-2">
                  <div className="text-slate-500">{"// Primary Provider: Ollama (llama3.1)"}</div>
                  <div className="text-emerald-400">{"Circuit State: CLOSED (0 failures recorded)"}</div>
                  <div className="text-slate-400">{"Cache Status: HIT (Returned from Redis in 4.2ms)"}</div>
                </div>
              </div>
            )}

            {activeTab === "observability" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-mono text-amber-400 font-semibold">GET /v1/stream (WebSocket Live Telemetry)</span>
                  <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    CONNECTED
                  </span>
                </div>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-2">
                  <div className="text-amber-400">{"[span] trace_id=t-901 span_id=s-12 service=router operation=chat_completions status=ok duration=12ms"}</div>
                  <div className="text-cyan-400">{"[span] trace_id=t-901 span_id=s-13 service=agents operation=mission_execution status=ok duration=142ms"}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* CTA Footer Banner */}
      <section className="relative z-10 py-20 border-t border-slate-800/80 bg-gradient-to-b from-[#080B11] to-[#04060A]">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <h2 className="text-4xl md:text-5xl font-black text-white mb-6">
            Ready to Build Your AI Infrastructure?
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto mb-10 text-base">
            Spin up the complete 4-microservice stack in under 30 seconds with Docker Compose.
          </p>

          <Link
            href="/app"
            className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 text-white font-bold text-lg shadow-xl shadow-cyan-500/25 hover:scale-[1.03] active:scale-[0.98] transition-all"
          >
            <span>Launch Dashboard Console</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-900 bg-[#04060A] py-8 text-center font-mono text-xs text-slate-600">
        <p>Tricore AI Builder Stack — Designed for Scalable Autonomous Infrastructure</p>
      </footer>
    </div>
  );
}
