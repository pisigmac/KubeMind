"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Zap, Cpu, Network, Activity, ShieldCheck, Terminal, 
  ArrowRight, CheckCircle2, ChevronRight, Layers, Sparkles,
  Command, Code2, Database, BarChart3, Bot, Compass, RefreshCw,
  Lock, Server, Sliders, DollarSign, Users, Check, Copy, ExternalLink,
  Eye, EyeOff, Flame, ShieldAlert, Coins, Scale, FileText, CheckCheck,
  Star, Globe, Building, Rocket, HelpCircle
} from "lucide-react";

export default function PreLaunchLandingPage() {
  // Pre-launch Waitlist state
  const [email, setEmail] = useState("");
  const [teamSize, setTeamSize] = useState("1-10");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [waitlistNumber, setWaitlistNumber] = useState(413);
  const [referralCode, setReferralCode] = useState("pioneer-413");
  const [stats, setStats] = useState({ total_signups: 412, target: 500 });

  // Load initial waitlist count
  useEffect(() => {
    fetch("/api/waitlist")
      .then((res) => res.json())
      .then((data) => {
        if (data?.total_signups) {
          setStats(data);
        }
      })
      .catch(() => {});
  }, []);

  // Interactive Sandbox Tab
  const [activeTab, setActiveTab] = useState<"privacy" | "roi" | "models" | "ledger">("privacy");

  // Privacy Redactor simulator state
  const [inputPrompt, setInputPrompt] = useState("Send quarterly report to john.smith@acmecorp.com with secret key sk-live-998821 and SSN 123-45-6789.");
  const [isRedactedView, setIsRedactedView] = useState(true);

  // ROI Calculator state
  const [monthlyRequests, setMonthlyRequests] = useState(500000); // 500k reqs
  const [avgTokensPerReq, setAvgTokensPerReq] = useState(800);
  const [cacheHitRate, setCacheHitRate] = useState(45); // 45% cache rate

  // Dynamic calculations
  const totalTokens = (monthlyRequests * avgTokensPerReq);
  const rawCost = (totalTokens * 0.000003); // ~$3 / 1M tokens baseline
  const savedViaCache = rawCost * (cacheHitRate / 100);
  const savedViaSmartRouting = (rawCost - savedViaCache) * 0.35; // 35% saved routing to cheaper/local models
  const totalMonthlySpend = rawCost - savedViaCache - savedViaSmartRouting;
  const netMonthlySavings = rawCost - totalMonthlySpend;
  const netAnnualSavings = netMonthlySavings * 12;

  // FAQ Accordion state
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const handleWaitlistSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes("@")) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, team_size: teamSize }),
      });
      const data = await res.json();
      if (data?.position) {
        setWaitlistNumber(data.position);
      }
      if (data?.referral_code) {
        setReferralCode(data.referral_code);
      }
      setSubmitted(true);
    } catch {
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  const copyReferral = () => {
    navigator.clipboard.writeText(`https://kubemind.io/prelaunch?ref=${referralCode}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="min-h-screen bg-[#070A0F] text-slate-100 font-sans selection:bg-cyan-500 selection:text-black overflow-x-hidden">
      {/* Dynamic Background Mesh Gradients */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-15%] left-[15%] w-[650px] h-[650px] bg-cyan-600/10 rounded-full blur-[150px]" />
        <div className="absolute top-[35%] right-[-5%] w-[550px] h-[550px] bg-indigo-600/10 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-10%] left-[5%] w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[150px]" />
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:28px_28px] opacity-25" />
      </div>

      {/* Top Pre-launch Alert Banner */}
      <div className="relative z-50 bg-gradient-to-r from-cyan-950/90 via-indigo-950/90 to-purple-950/90 border-b border-cyan-800/40 px-4 py-2.5 text-center text-xs sm:text-sm font-medium text-cyan-200">
        <span className="inline-flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
          </span>
          <span className="font-bold text-white uppercase tracking-wider text-[11px] bg-cyan-500/20 px-2 py-0.5 rounded border border-cyan-400/30">Pre-Launch Batch #1</span>
          <span>Early Pioneer Program is Open · <strong>412 of 500</strong> Founding Slots Claimed!</span>
          <a href="#waitlist" className="underline font-bold text-white hover:text-cyan-300 ml-1">Lock 50% Lifetime Discount &rarr;</a>
        </span>
      </div>

      {/* Sticky Header Navbar */}
      <header className="relative z-40 border-b border-slate-800/80 backdrop-blur-xl bg-[#070A0F]/80 sticky top-0">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-emerald-400 p-[1px] shadow-lg shadow-cyan-500/20">
              <div className="w-full h-full bg-[#0B0F19] rounded-[11px] flex items-center justify-center">
                <Cpu className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <span className="text-xl font-black tracking-wider text-white font-mono">KUBEMIND</span>
              <span className="ml-2 text-[10px] uppercase font-bold tracking-widest text-cyan-400 bg-cyan-950/80 border border-cyan-800/50 px-2 py-0.5 rounded-full">Sovereign Gateway</span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-400 font-medium">
            <a href="#sandbox" className="hover:text-cyan-400 transition-colors">Interactive Sandbox</a>
            <a href="#pillars" className="hover:text-cyan-400 transition-colors">Architecture</a>
            <a href="#roi" className="hover:text-cyan-400 transition-colors">Cost Calculator</a>
            <a href="#tiers" className="hover:text-cyan-400 transition-colors">Founding Tiers</a>
            <a href="#faq" className="hover:text-cyan-400 transition-colors">FAQ</a>
          </nav>

          <div className="flex items-center gap-3">
            <Link 
              href="/"
              className="hidden sm:inline-flex px-4 py-2 rounded-xl text-xs font-bold text-slate-300 hover:text-white hover:bg-slate-800/60 border border-slate-700/60 transition-all"
            >
              Live Cluster Status
            </Link>
            <a 
              href="#waitlist" 
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-xs sm:text-sm shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-2 group"
            >
              <span>Get VIP Access</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-16 pb-24 max-w-7xl mx-auto px-6 text-center">
        {/* Pill Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-slate-300 text-xs font-mono mb-8 shadow-inner">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span>Zero-Egress Privacy</span>
          <span className="text-slate-600">·</span>
          <span>Dynamic Model Sync</span>
          <span className="text-slate-600">·</span>
          <span className="text-cyan-400 font-semibold">SHA-256 Ledger</span>
        </div>

        {/* Hero Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-5xl mx-auto leading-[1.1] mb-6">
          The Sovereign AI Gateway & <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-cyan-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
            Governance Runtime for LLMs
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-400 max-w-3xl mx-auto font-normal leading-relaxed mb-10">
          Mask sensitive PII before prompts leave your VPC, slash 40–70% of LLM bills via semantic vector caching, and cryptographically seal every token in a tamper-evident audit ledger.
        </p>

        {/* Waitlist Capture Card */}
        <div id="waitlist" className="max-w-2xl mx-auto p-6 sm:p-8 rounded-3xl bg-slate-900/90 border border-slate-800/90 shadow-2xl backdrop-blur-xl text-left relative overflow-hidden mb-12">
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-cyan-500/10 to-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

          {!submitted ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Rocket className="w-5 h-5 text-cyan-400" />
                    <span>Join Pre-Launch Pioneer Program</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">Claim priority access, free self-host license & 50% lifetime discount.</p>
                </div>
                <span className="hidden sm:inline-block px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-800/60 text-emerald-400 font-mono text-xs font-bold">
                  88 Slots Left
                </span>
              </div>

              <form onSubmit={handleWaitlistSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Work Email</label>
                    <input 
                      type="email" 
                      required
                      placeholder="alex@enterprise.com" 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Team Size</label>
                    <select 
                      value={teamSize}
                      onChange={(e) => setTeamSize(e.target.value)}
                      className="w-full px-3 py-3 rounded-xl bg-slate-950 border border-slate-700 text-white text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                    >
                      <option value="1-5">1 - 5 Devs</option>
                      <option value="5-20">5 - 20 Devs</option>
                      <option value="20-100">20 - 100 Devs</option>
                      <option value="100+">100+ Enterprise</option>
                    </select>
                  </div>
                </div>

                <button 
                  type="submit"
                  className="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 text-white font-bold text-sm shadow-xl shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:scale-[1.01] active:scale-[0.99] transition-all flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Lock Founding Member Perks &rarr;</span>
                </button>
              </form>

              <div className="mt-4 flex flex-wrap items-center justify-between text-[11px] text-slate-500 gap-2">
                <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Instant Docker Compose Blueprint</span>
                <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Free OpenDesk & PayDeck Integration</span>
                <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> No Credit Card Required</span>
              </div>
            </div>
          ) : (
            <div className="p-4 text-center space-y-4">
              <div className="w-12 h-12 bg-emerald-500/20 border border-emerald-400/40 rounded-full flex items-center justify-center mx-auto text-emerald-400">
                <CheckCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">You&apos;re On the VIP Pioneer List!</h3>
                <p className="text-sm text-slate-300 mt-1">
                  You are reserved at <span className="font-bold text-cyan-400 font-mono">#{waitlistNumber}</span> in line.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 max-w-lg mx-auto text-left">
                <p className="text-xs font-semibold text-slate-400 mb-1.5">Your Founding Pioneer Referral Link:</p>
                <div className="flex items-center gap-2">
                  <input 
                    readOnly
                    value={`https://kubemind.io/prelaunch?ref=pioneer-${waitlistNumber}`}
                    className="flex-1 bg-slate-900 px-3 py-2 rounded-lg text-xs font-mono text-cyan-300 border border-slate-800"
                  />
                  <button 
                    onClick={copyReferral}
                    className="px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-1 transition-all"
                  >
                    {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                </div>
                <p className="text-[11px] text-slate-500 mt-2">
                  Invite 2 teammates to jump 50 spots ahead and unlock immediate Private Beta keys.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Supported Models Bar */}
        <div className="pt-4 max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest text-slate-500 font-mono font-bold mb-6">
            Native Support Across Local & Cloud LLM Ecosystems
          </p>
          <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-10 text-slate-400 text-xs sm:text-sm font-semibold opacity-80">
            <span className="flex items-center gap-2 hover:text-white transition-colors">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span> Google Gemini 2.5 / 3.1
            </span>
            <span className="flex items-center gap-2 hover:text-white transition-colors">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span> OpenAI GPT-4o / o1 / o3
            </span>
            <span className="flex items-center gap-2 hover:text-white transition-colors">
              <span className="w-2 h-2 rounded-full bg-purple-400"></span> Ollama (Llama 3.3 & DeepSeek)
            </span>
            <span className="flex items-center gap-2 hover:text-white transition-colors">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span> Groq LPU Ultra-Low Latency
            </span>
            <span className="flex items-center gap-2 hover:text-white transition-colors">
              <span className="w-2 h-2 rounded-full bg-indigo-400"></span> Anthropic Claude 3.7
            </span>
          </div>
        </div>
      </section>

      {/* Interactive Sandbox Section */}
      <section id="sandbox" className="py-20 bg-slate-950/60 border-y border-slate-900 relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-950/80 px-3 py-1 rounded-full border border-cyan-800/50">
              Hands-On Interactive Teaser
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-4 mb-3">
              Experience the KubeMind Difference
            </h2>
            <p className="text-sm text-slate-400">
              Test how KubeMind handles sensitive enterprise payloads, optimizes token economics, and dynamically maps model families in real-time.
            </p>
          </div>

          {/* Sandbox Tabs */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            <button
              onClick={() => setActiveTab("privacy")}
              className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition-all ${
                activeTab === "privacy"
                  ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/25"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              <Lock className="w-4 h-4" />
              <span>Zero-Egress PII Redactor</span>
            </button>
            <button
              onClick={() => setActiveTab("roi")}
              className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition-all ${
                activeTab === "roi"
                  ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/25"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              <DollarSign className="w-4 h-4" />
              <span>Cost & Cache ROI Calculator</span>
            </button>
            <button
              onClick={() => setActiveTab("models")}
              className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition-all ${
                activeTab === "models"
                  ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/25"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              <RefreshCw className="w-4 h-4" />
              <span>Dynamic Upstream Sync</span>
            </button>
            <button
              onClick={() => setActiveTab("ledger")}
              className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition-all ${
                activeTab === "ledger"
                  ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/25"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>SHA-256 Merkle Ledger</span>
            </button>
          </div>

          {/* Tab 1: Privacy Sandbox */}
          {activeTab === "privacy" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl mx-auto">
              <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-400"></span> Input Prompt (Internal User)
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">Editable</span>
                </div>
                <textarea
                  value={inputPrompt}
                  onChange={(e) => setInputPrompt(e.target.value)}
                  rows={4}
                  className="w-full p-3.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
                <div className="mt-4 p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs text-slate-400 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span>Detected Entities:</span>
                    <span className="text-cyan-400 font-mono font-bold">1 Email, 1 API Key, 1 SSN</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Policy Action:</span>
                    <span className="text-emerald-400 font-bold">REDACT_FOR_EGRESS (Zero-Egress Active)</span>
                  </div>
                </div>
              </div>

              <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5" /> What External Cloud LLM Sees
                    </span>
                    <span className="text-[11px] bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded font-mono">
                      Masked Stream
                    </span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-purple-900/50 font-mono text-sm text-purple-300 space-y-2">
                    <p>
                      Send quarterly report to <span className="bg-purple-900/60 text-purple-200 px-1 py-0.5 rounded font-bold">[KM_EMAIL_1]</span> with secret key <span className="bg-purple-900/60 text-purple-200 px-1 py-0.5 rounded font-bold">[KM_SECRET_1]</span> and SSN <span className="bg-purple-900/60 text-purple-200 px-1 py-0.5 rounded font-bold">[KM_SSN_1]</span>.
                    </p>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-800">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Restored Response to Client:</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Automatically Reversed In-Memory
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: ROI Calculator */}
          {activeTab === "roi" && (
            <div className="max-w-5xl mx-auto p-8 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-2xl">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
                <div className="space-y-6">
                  <div>
                    <div className="flex justify-between text-xs font-bold text-slate-300 mb-2">
                      <span>Monthly Request Volume</span>
                      <span className="font-mono text-cyan-400">{(monthlyRequests / 1000).toLocaleString()}K requests/mo</span>
                    </div>
                    <input 
                      type="range" 
                      min="50000" 
                      max="5000000" 
                      step="50000"
                      value={monthlyRequests} 
                      onChange={(e) => setMonthlyRequests(Number(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-bold text-slate-300 mb-2">
                      <span>Avg Tokens per Turn (Prompt + Output)</span>
                      <span className="font-mono text-cyan-400">{avgTokensPerReq} tokens</span>
                    </div>
                    <input 
                      type="range" 
                      min="200" 
                      max="4000" 
                      step="100"
                      value={avgTokensPerReq} 
                      onChange={(e) => setAvgTokensPerReq(Number(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-bold text-slate-300 mb-2">
                      <span>Expected Semantic Cache Hit Rate</span>
                      <span className="font-mono text-emerald-400">{cacheHitRate}% cache hits</span>
                    </div>
                    <input 
                      type="range" 
                      min="15" 
                      max="75" 
                      step="5"
                      value={cacheHitRate} 
                      onChange={(e) => setCacheHitRate(Number(e.target.value))}
                      className="w-full accent-emerald-400"
                    />
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-slate-950 border border-slate-800 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-slate-400">Direct Cloud LLM Cost:</span>
                      <span className="text-rose-400 font-mono font-bold line-through">${Math.round(rawCost).toLocaleString()} / mo</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-slate-400">Semantic Cache Savings:</span>
                      <span className="text-emerald-400 font-mono font-bold">-${Math.round(savedViaCache).toLocaleString()} / mo</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-slate-400">Intent Routing Optimization:</span>
                      <span className="text-cyan-400 font-mono font-bold">-${Math.round(savedViaSmartRouting).toLocaleString()} / mo</span>
                    </div>
                    <div className="pt-4 border-t border-slate-800 flex justify-between items-center">
                      <span className="text-base font-bold text-white">Net Annual Savings:</span>
                      <span className="text-3xl font-extrabold font-mono text-emerald-400">
                        ${Math.round(netAnnualSavings).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-4">
                    *Calculated based on standard model blend rates (Gemini 2.5, GPT-4o, and local Ollama Llama 3.3).
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Tab 3: Model Sync Sandbox */}
          {activeTab === "models" && (
            <div className="max-w-4xl mx-auto p-6 rounded-2xl bg-[#090D16] border border-slate-800 font-mono text-xs text-slate-300">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
                <span className="text-cyan-400 font-bold">$ kmind sync-models</span>
                <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" /> Live Gateway Sync
                </span>
              </div>
              <pre className="text-slate-300 whitespace-pre-wrap leading-relaxed">
{`====================================================================
       🔄 KubeMind Upstream Dynamic Model Catalog Sync             
====================================================================
  Gateway Endpoint:  http://localhost:9080
  Active Workspace:  production

  Scanning live /models APIs across OpenAI, Gemini, Groq, Ollama...

  PROVIDER         STATUS     COST     DISCOVERED   SAMPLE MODELS                   
  ────────────────────────────────────────────────────────────────────────────────
  google           ONLINE     FREE     +51 live     gemini-2.5-flash, gemini-3.1-pro-preview...
  ollama           ONLINE     FREE     +2 live      llama3.1, nomic-embed-text...
  openai           ONLINE     PAID     +118 live    gpt-4o, gpt-4o-mini, o1, o3-mini...
  ────────────────────────────────────────────────────────────────────────────────
  ✓ Total Models Registered: 182 across all active providers.
  💡 Auto-intent routing maps code -> Gemini/DeepSeek and rag -> Mind pgvector.`}
              </pre>
            </div>
          )}

          {/* Tab 4: Merkle Ledger */}
          {activeTab === "ledger" && (
            <div className="max-w-4xl mx-auto p-6 rounded-2xl bg-slate-900/90 border border-slate-800">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Sentinel SHA-256 Hash-Chained Audit Blocks</span>
                </span>
                <span className="text-xs font-mono text-cyan-400">kmind verify</span>
              </div>
              <div className="space-y-3 font-mono text-xs">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 space-y-1">
                  <div className="flex justify-between text-slate-500">
                    <span>Block #1492</span>
                    <span>2026-08-26 17:35:10 UTC</span>
                  </div>
                  <p className="text-cyan-300 truncate">Entry SHA-256: 25db94112a555ea32c77ca52f1200b699f07dd7444fdfbdee44ea18e822f24c3</p>
                  <p className="text-slate-500 text-[11px]">Payload: &#123;&quot;intent&quot;: &quot;code&quot;, &quot;model&quot;: &quot;gemini-2.5-flash&quot;, &quot;tokens&quot;: 131, &quot;policy&quot;: &quot;allow&quot;&#125;</p>
                </div>
                <div className="flex justify-center text-slate-600">↓ linked via SHA-256 prev_hash</div>
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 space-y-1">
                  <div className="flex justify-between text-slate-500">
                    <span>Block #1493 (Head)</span>
                    <span>2026-08-26 17:35:14 UTC</span>
                  </div>
                  <p className="text-emerald-400 truncate">Entry SHA-256: a8b39c011fe6425a817b3c033dc1aa26dfb00a2426125489cf586116e6c6b772</p>
                  <p className="text-slate-500 text-[11px]">Payload: &#123;&quot;intent&quot;: &quot;rag&quot;, &quot;retrieval_hits&quot;: 4, &quot;tokens&quot;: 1024, &quot;cost&quot;: 0.002048&#125;</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Core Architectural Pillars */}
      <section id="pillars" className="py-24 max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-950/80 px-3 py-1 rounded-full border border-cyan-800/50">
            Engineered For Sovereign AI
          </span>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white mt-4 mb-4">
            The 6 Pillars of AI Governance
          </h2>
          <p className="text-slate-400 text-base">
            Everything your enterprise needs to safely deploy, govern, and observe AI agents at scale.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Pillar 1 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-6 group-hover:scale-110 transition-transform">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Zero-Egress PII Redaction</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Inline NER models and pattern engines replace names, keys, and secrets with reversible tokens before prompts hit cloud LLMs, restoring them seamlessly in outputs.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-6 group-hover:scale-110 transition-transform">
              <Zap className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Semantic Vector Caching</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Dual-layer exact and semantic cache partitions responses by intent. Common queries return in 0ms at $0 cost, slashing up to 60% of monthly API spend.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-6 group-hover:scale-110 transition-transform">
              <Network className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Intent-Aware Model Router</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Dynamic classifier automatically evaluates prompt complexity, routing code to precision models, RAG to knowledge backends, and simple turns to local Ollama.
            </p>
          </div>

          {/* Pillar 4 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-purple-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-6 group-hover:scale-110 transition-transform">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Cryptographic SHA-256 Ledger</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Sentinel records every routing decision, token count, and policy action into an immutable Merkle hash chain for instant SOC2 and ISO27001 audit verification.
            </p>
          </div>

          {/* Pillar 5 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-amber-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-6 group-hover:scale-110 transition-transform">
              <Server className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Decoupled OpenDesk Auth</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Zero-database RS256 Bearer JWT verification against OpenDesk public JWKS. Fine-grained RBAC scopes mapped dynamically across all microservices.
            </p>
          </div>

          {/* Pillar 6 */}
          <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/50 transition-all group">
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-6 group-hover:scale-110 transition-transform">
              <Coins className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">PayDeck Metered Billing</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Integrated Razorpay subscriptions and automatic token meter top-ups. Real-time CFO rollups across multi-tenant workspaces.
            </p>
          </div>
        </div>
      </section>

      {/* Pre-Launch Founding Pioneer Tiers */}
      <section id="tiers" className="py-20 bg-slate-950/80 border-t border-slate-900">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/80 px-3 py-1 rounded-full border border-emerald-800/50">
              Founding Pioneer Program
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold text-white mt-4 mb-4">
              Lock Lifetime Pre-Launch Pricing
            </h2>
            <p className="text-slate-400 text-base">
              Early access members keep founding pricing forever with no future price escalations.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {/* Tier 1: Developer */}
            <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">Community Tier</span>
                <h3 className="text-2xl font-bold text-white mt-1">Founding Developer</h3>
                <div className="mt-4 mb-6">
                  <span className="text-4xl font-extrabold text-white">Free</span>
                  <span className="text-slate-400 text-sm"> / forever</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-300">
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Full Self-Hosted Docker Core</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Unlimited Local Ollama Routing</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> 500K Cloud Tokens / month</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Regex PII Redaction</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Community Discord Support</li>
                </ul>
              </div>
              <a href="#waitlist" className="mt-8 w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm text-center block transition-all">
                Join Community Waitlist
              </a>
            </div>

            {/* Tier 2: Pioneer Pro (Featured) */}
            <div className="p-8 rounded-3xl bg-gradient-to-b from-cyan-950/40 via-slate-900 to-indigo-950/40 border-2 border-cyan-500/80 flex flex-col justify-between relative shadow-2xl shadow-cyan-500/10">
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-cyan-500 text-black font-bold text-xs uppercase tracking-wider shadow-lg">
                Most Popular · 50% Off Early Bird
              </div>
              <div>
                <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider">Pioneer Pro</span>
                <h3 className="text-2xl font-bold text-white mt-1">Founding Team</h3>
                <div className="mt-4 mb-6 flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-white">₹1,999</span>
                  <span className="text-slate-400 text-sm line-through">₹3,999</span>
                  <span className="text-slate-400 text-sm">/ month</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-300">
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> <strong>15M Tokens</strong> / month included</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> <strong>Full Semantic Vector Caching</strong> (pgvector)</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> ONNX NER Zero-Egress Privacy Engine</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> SHA-256 Merkle Audit Ledger</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> OpenDesk Identity & PayDeck Checkout</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Priority 24/7 Support Channel</li>
                </ul>
              </div>
              <a href="#waitlist" className="mt-8 w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-bold text-sm text-center block shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all">
                Lock 50% Lifetime Price
              </a>
            </div>

            {/* Tier 3: Sovereign Enterprise */}
            <div className="p-8 rounded-3xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono font-bold text-purple-400 uppercase tracking-wider">Enterprise VPC</span>
                <h3 className="text-2xl font-bold text-white mt-1">Sovereign Cluster</h3>
                <div className="mt-4 mb-6">
                  <span className="text-4xl font-extrabold text-white">Custom</span>
                  <span className="text-slate-400 text-sm"> / annual contract</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-300">
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Unlimited Workspaces & Tenants</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> 100% Air-Gapped On-Premises Deployment</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Custom KeyMint KMS / HSM Integration</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Custom SOC2 / HIPAA Compliance Bundles</li>
                  <li className="flex items-center gap-2.5"><Check className="w-4 h-4 text-cyan-400" /> Dedicated Solutions Architect</li>
                </ul>
              </div>
              <a href="#waitlist" className="mt-8 w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm text-center block transition-all">
                Request Architecture Consultation
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Pre-launch FAQ Section */}
      <section id="faq" className="py-20 max-w-4xl mx-auto px-6">
        <div className="text-center mb-12">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-950/80 px-3 py-1 rounded-full border border-cyan-800/50">
            Frequently Asked Questions
          </span>
          <h2 className="text-3xl font-extrabold text-white mt-4 mb-2">
            Pre-Launch & Architecture Details
          </h2>
        </div>

        <div className="space-y-4">
          {[
            {
              q: "How does Zero-Egress Reversible Pseudonymization work?",
              a: "When a user sends a prompt, KubeMind's inline NER engine detects PII, secrets, and credentials, replacing them with tokens like [KM_PERSON_1] before transmitting to external providers (Gemini, OpenAI, Groq). When the response streams back, tokens are seamlessly swapped back in-memory so real names appear to the client with zero cloud data leakage."
            },
            {
              q: "Can KubeMind run 100% locally without cloud connections?",
              a: "Yes! KubeMind includes native Ollama and vLLM providers. You can route coding to DeepSeek, general chat to Llama 3.3, and embeddings to nomic-embed-text entirely on local GPU/CPU hardware with zero external egress."
            },
            {
              q: "How does KubeMind integrate with OpenDesk and PayDeck?",
              a: "OpenDesk issues RS256-signed JWTs which KubeMind validates against OpenDesk's public JWKS with zero database calls. PayDeck manages Razorpay subscription orders and token metering top-ups via webhook dispatch."
            },
            {
              q: "What is included in the Pre-Launch Pioneer Program?",
              a: "Founding members receive immediate Docker Compose clusters, lifetime 50% discount locks on Pro plans, access to the private developer Discord, and priority roadmap voting."
            }
          ].map((item, idx) => (
            <div 
              key={idx} 
              className="rounded-2xl bg-slate-900/70 border border-slate-800/80 overflow-hidden transition-all"
            >
              <button
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                className="w-full p-5 text-left font-bold text-white flex justify-between items-center text-sm sm:text-base hover:text-cyan-400 transition-colors"
              >
                <span>{item.q}</span>
                <ChevronRight className={`w-4 h-4 text-cyan-400 transition-transform ${openFaq === idx ? "rotate-90" : ""}`} />
              </button>
              {openFaq === idx && (
                <div className="p-5 pt-0 text-sm text-slate-400 leading-relaxed border-t border-slate-800/50 mt-1">
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="py-16 bg-gradient-to-t from-cyan-950/40 to-transparent border-t border-slate-900 text-center">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-4">
            Ready to Take Control of Your AI Infrastructure?
          </h2>
          <p className="text-slate-400 text-sm sm:text-base max-w-xl mx-auto mb-8">
            Join 400+ developers and engineering leaders preparing for the KubeMind Sovereign Gateway launch.
          </p>
          <a
            href="#waitlist"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 text-white font-bold text-base shadow-xl shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            <Sparkles className="w-5 h-5" />
            <span>Join Pre-Launch Pioneer Program &rarr;</span>
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-[#05070B] py-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2 text-slate-400 font-mono font-bold">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>KUBEMIND SOVEREIGN AI CORE</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/" className="hover:text-cyan-400 transition-colors">Cluster Console</Link>
            <Link href="/gateway" className="hover:text-cyan-400 transition-colors">Gateway Stats</Link>
            <Link href="/observability" className="hover:text-cyan-400 transition-colors">Audit Ledger</Link>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-cyan-400 transition-colors">GitHub</a>
          </div>
          <p>&copy; {new Date().getFullYear()} KubeMind Sovereign Systems. OpenDesk & PayDeck Integrated.</p>
        </div>
      </footer>
    </div>
  );
}
