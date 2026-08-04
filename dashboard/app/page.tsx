"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { routerApi, mindApi, agentsApi, sentinelApi } from "@/lib/api";
import { 
  Activity, Network, Database, Bot, BarChart3, CheckCircle2, XCircle, Loader2, Zap, ArrowUpRight, Cpu
} from "lucide-react";

interface ServiceStatus {
  name: string;
  healthy: boolean;
  version: string;
  loading: boolean;
  port: string;
  icon: any;
}

export default function HomePage() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: "Router Gateway", healthy: false, version: "-", loading: true, port: "9080", icon: Network },
    { name: "Mind Context", healthy: false, version: "-", loading: true, port: "9081", icon: Database },
    { name: "Agents Planner", healthy: false, version: "-", loading: true, port: "9082", icon: Bot },
    { name: "Sentinel Tracer", healthy: false, version: "-", loading: true, port: "9083", icon: BarChart3 },
  ]);
  const [usage, setUsage] = useState<any>(null);
  const [missions, setMissions] = useState<any[]>([]);
  const [sentinelStats, setSentinelStats] = useState<any>(null);

  useEffect(() => {
    async function checkAll() {
      const checks = await Promise.allSettled([
        routerApi.health().catch(() => null),
        mindApi.health().catch(() => null),
        agentsApi.health().catch(() => null),
        sentinelApi.health().catch(() => null),
      ]);

      const serviceMeta = [
        { name: "Router Gateway", port: "9080", icon: Network },
        { name: "Mind Context", port: "9081", icon: Database },
        { name: "Agents Planner", port: "9082", icon: Bot },
        { name: "Sentinel Tracer", port: "9083", icon: BarChart3 },
      ];

      setServices(
        checks.map((result, i) => {
          const meta = serviceMeta[i];
          if (result.status === "fulfilled" && result.value) {
            return {
              ...meta,
              healthy: result.value.status === "healthy",
              version: result.value.version || "0.1.0",
              loading: false,
            };
          }
          return { ...meta, healthy: false, version: "-", loading: false };
        })
      );
    }

    checkAll();
    const interval = setInterval(checkAll, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    routerApi.usage().then(setUsage).catch(() => {});
    agentsApi.missions(5).then(setMissions).catch(() => {});
    sentinelApi.stats().then(setSentinelStats).catch(() => {});
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Overview Header Banner */}
      <div className="p-8 rounded-3xl bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-2xl relative overflow-hidden">
        <div className="space-y-2 relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Activity className="w-3.5 h-3.5" />
            <span>KubeMind Platform Control Plane</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Enterprise Infrastructure Status</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Real-time monitoring across LLM gateway proxies, hybrid vector memory, autonomous agents, and telemetry daemons.
          </p>
        </div>
        <div className="flex items-center gap-3 relative z-10">
          <div className="px-4 py-2 rounded-xl bg-[#090D16] border border-[#1E293B] font-mono text-xs text-slate-300">
            Status: <span className="text-emerald-400 font-bold">ALL SYSTEMS GO</span>
          </div>
        </div>
      </div>

      {/* 4 Microservice Cluster Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {services.map((svc) => {
          const Icon = svc.icon;
          return (
            <Card key={svc.name} className="p-6 bg-[#0F172A] border border-[#1E293B] hover:border-[#0066FF]/50 transition-all shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-[#0066FF]/15 border border-[#0066FF]/30 flex items-center justify-center text-[#0066FF]">
                  <Icon className="w-5 h-5" />
                </div>
                {svc.loading ? (
                  <span className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0066FF]" />
                    Checking...
                  </span>
                ) : svc.healthy ? (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    ONLINE
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono font-bold flex items-center gap-1.5">
                    OFFLINE
                  </span>
                )}
              </div>

              <h3 className="font-bold text-lg text-white mb-1">{svc.name}</h3>
              <div className="flex justify-between items-center text-xs font-mono text-slate-400">
                <span>Port: :{svc.port}</span>
                <span className="text-slate-500">v{svc.version}</span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Detail Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Gateway Card */}
        <Card className="p-6 bg-[#0F172A] border border-[#1E293B]">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E293B]">
            <div className="flex items-center gap-3">
              <Network className="w-5 h-5 text-[#0066FF]" />
              <h2 className="font-bold text-base text-white">Gateway Usage</h2>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-[#1E293B] px-2.5 py-1 rounded-lg">:9080</span>
          </div>

          {usage ? (
            <div className="space-y-4 font-mono text-xs">
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Total Requests:</span>
                <span className="font-bold text-white">{usage.total_requests || 0}</span>
              </div>
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Tokens Processed:</span>
                <span className="font-bold text-white">{usage.total_tokens || 0}</span>
              </div>
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Estimated Cost:</span>
                <span className="font-bold text-emerald-400">${(usage.estimated_cost || 0).toFixed(4)}</span>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-slate-500 font-mono">No usage data logged yet</div>
          )}
        </Card>

        {/* Missions Card */}
        <Card className="p-6 bg-[#0F172A] border border-[#1E293B]">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E293B]">
            <div className="flex items-center gap-3">
              <Bot className="w-5 h-5 text-[#0066FF]" />
              <h2 className="font-bold text-base text-white">Recent Missions</h2>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-[#1E293B] px-2.5 py-1 rounded-lg">:9082</span>
          </div>

          {missions.length > 0 ? (
            <div className="space-y-3 font-mono text-xs">
              {missions.slice(0, 5).map((m) => (
                <div key={m.id} className="flex items-center justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                  <span className="truncate max-w-[170px] text-slate-200 font-semibold">{m.prompt}</span>
                  <StatusPill status={m.status} />
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-slate-500 font-mono">No recent missions executing</div>
          )}
        </Card>

        {/* Sentinel Card */}
        <Card className="p-6 bg-[#0F172A] border border-[#1E293B]">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E293B]">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5 text-[#0066FF]" />
              <h2 className="font-bold text-base text-white">Sentinel Spans</h2>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-[#1E293B] px-2.5 py-1 rounded-lg">:9083</span>
          </div>

          {sentinelStats ? (
            <div className="space-y-4 font-mono text-xs">
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Total Spans Tracked:</span>
                <span className="font-bold text-white">{sentinelStats.total_spans || 0}</span>
              </div>
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Active Workspaces:</span>
                <span className="font-bold text-white">{sentinelStats.workspaces || 0}</span>
              </div>
              <div className="flex justify-between p-3 rounded-xl bg-[#090D16] border border-[#1E293B]">
                <span className="text-slate-400">Services Connected:</span>
                <span className="font-bold text-[#0066FF]">{sentinelStats.services || 0}</span>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-slate-500 font-mono">No trace spans recorded yet</div>
          )}
        </Card>
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
