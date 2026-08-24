"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { routerApi } from "@/lib/api";
import { Network, Zap, ShieldCheck, Database, Loader2, Sparkles, RefreshCw, Trash2 } from "lucide-react";

interface ProviderHealth {
  name: string;
  healthy: boolean;
  circuit_state: string;
  models: string[];
  priority: number;
  free: boolean;
  failure_count: number;
}

export default function GatewayPage() {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [usage, setUsage] = useState<any>(null);
  const [cacheStats, setCacheStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [healthData, usageData, cacheData] = await Promise.allSettled([
        routerApi.providers(),
        routerApi.usage(),
        routerApi.cacheStats(),
      ]);

      if (healthData.status === "fulfilled") {
        setProviders(Array.isArray(healthData.value) ? healthData.value : []);
      }
      if (usageData.status === "fulfilled") {
        setUsage(usageData.value);
      }
      if (cacheData.status === "fulfilled") {
        setCacheStats(cacheData.value);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  async function clearCache() {
    try {
      await fetch("/api/router/v1/cache/clear", { method: "POST" });
      await loadData();
    } catch (err: any) {
      alert("Failed: " + err.message);
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-8 rounded-3xl bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Network className="w-3.5 h-3.5" />
            <span>KubeMind Router Proxy</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Gateway Router Console</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Multi-provider failover, model load balancing, and Redis prompt deduplication caching (&lt;10ms).
          </p>
        </div>
      </div>

      {loading && (
        <Card className="p-8 text-center bg-[#0F172A] border border-[#1E293B]">
          <Loader2 className="w-6 h-6 animate-spin text-[#0066FF] mx-auto mb-2" />
          <p className="text-xs text-slate-400 font-mono">Querying LLM provider health status...</p>
        </Card>
      )}

      {/* Provider Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {providers.map((p) => (
          <Card key={p.name} className="p-6 bg-[#0F172A] border border-[#1E293B] hover:border-[#0066FF]/50 transition-all shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-white text-base">
                <span>{p.name}</span>
                {p.free && (
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full font-mono">
                    Free / Local
                  </span>
                )}
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${p.healthy ? "bg-emerald-400 animate-ping" : "bg-rose-500"}`} />
            </div>

            <div className="space-y-3 font-mono text-xs text-slate-300">
              <div className="flex justify-between p-2.5 rounded-lg bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-500">Priority Tier:</span>
                <span className="font-bold text-white">{p.priority}</span>
              </div>
              <div className="flex justify-between p-2.5 rounded-lg bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-500">Circuit State:</span>
                <span className={`font-bold uppercase ${p.circuit_state === "closed" ? "text-emerald-400" : "text-rose-400"}`}>
                  {p.circuit_state}
                </span>
              </div>
              <div className="flex justify-between p-2.5 rounded-lg bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-500">Failures:</span>
                <span className="font-bold text-white">{p.failure_count}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-[#090D16] border border-[#1E293B] truncate">
                <span className="text-slate-500 block mb-1">Available Models:</span>
                <span className="font-bold text-[#0066FF]">{p.models.join(", ") || "Default"}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Analytics & Redis Cache Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {usage && (
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-[#0066FF]" />
                <h2 className="font-bold text-lg text-white">Aggregated Usage Summary</h2>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center font-mono">
              <div className="p-4 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <div className="text-2xl font-black text-white">{usage.total_requests || 0}</div>
                <div className="text-[11px] text-slate-400 mt-1 uppercase font-bold">Total Requests</div>
              </div>
              <div className="p-4 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <div className="text-2xl font-black text-white">{usage.total_tokens || 0}</div>
                <div className="text-[11px] text-slate-400 mt-1 uppercase font-bold">Tokens Tracked</div>
              </div>
              <div className="p-4 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <div className="text-2xl font-black text-emerald-400">${(usage.estimated_cost || 0).toFixed(4)}</div>
                <div className="text-[11px] text-slate-400 mt-1 uppercase font-bold">Est. API Cost</div>
              </div>
            </div>

            {usage.providers && Object.keys(usage.providers).length > 0 && (
              <div className="space-y-2 font-mono text-xs">
                {Object.entries(usage.providers).map(([name, data]: [string, any]) => (
                  <div key={name} className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                    <span className="text-slate-300 font-bold">{name}</span>
                    <span className="text-slate-400">{data.requests} req, {data.tokens} tok</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {cacheStats && (
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-[#0066FF]" />
                <h2 className="font-bold text-lg text-white">Redis Deduplication Cache</h2>
              </div>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                cacheStats.connected ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/10 text-rose-400"
              }`}>
                {cacheStats.connected ? "CONNECTED" : "DISCONNECTED"}
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Cache Connection:</span>
                <span className="font-bold text-emerald-400">{cacheStats.connected ? "Active (:9379)" : "Inactive"}</span>
              </div>
              {cacheStats.keys_in_db !== undefined && (
                <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                  <span className="text-slate-400">Cached Prompt Keys:</span>
                  <span className="font-bold text-white">{cacheStats.keys_in_db}</span>
                </div>
              )}
              {cacheStats.used_memory_human && (
                <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                  <span className="text-slate-400">Memory Allocation:</span>
                  <span className="font-bold text-[#0066FF]">{cacheStats.used_memory_human}</span>
                </div>
              )}
            </div>

            <button 
              onClick={clearCache} 
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-bold font-mono transition-all"
            >
              <Trash2 className="w-4 h-4" />
              <span>Purge Redis Cache Keys</span>
            </button>
          </Card>
        )}
      </div>
    </div>
  );
}
