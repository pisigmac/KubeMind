"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { sentinelApi } from "@/lib/api";
import { useSentinelStream } from "@/lib/ws";
import { Activity, Radio, AlertCircle, Clock, Cpu, Zap, Layers } from "lucide-react";

interface Span {
  id: number;
  service: string;
  operation: string;
  status: string;
  created_at: string;
  attributes: any;
}

export default function ObservabilityPage() {
  const [spans, setSpans] = useState<Span[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [hours, setHours] = useState(24);
  const { connected, spans: liveSpans } = useSentinelStream("default");

  async function loadData() {
    try {
      const [spansData, metricsData] = await Promise.all([
        sentinelApi.spans("default", 50),
        sentinelApi.metrics("default", hours),
      ]);
      setSpans(spansData.spans || []);
      setMetrics(metricsData);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [hours]);

  // Merge live spans with fetched spans
  const allSpans = [...liveSpans.map((s: any) => ({
    id: s.span_id || Date.now(),
    service: s.service,
    operation: s.operation,
    status: s.status,
    created_at: s.start_time,
    attributes: s.attributes,
  })), ...spans].slice(0, 100);

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-8 rounded-3xl bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Activity className="w-3.5 h-3.5" />
            <span>Sentinel Telemetry Daemon</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Real-Time Observability</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Live trace span ingestion, WebSocket event streams, and error tracking across all microservice engines.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 font-mono text-xs">
            {connected ? (
              <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                WebSocket Live Stream
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 font-bold flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                Stream Offline
              </span>
            )}
          </div>

          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="px-3 py-2 bg-[#090D16] border border-[#1E293B] rounded-xl text-xs font-mono font-bold text-white focus:outline-none focus:border-[#0066FF]"
          >
            <option value={1}>Last 1 Hour</option>
            <option value={6}>Last 6 Hours</option>
            <option value={24}>Last 24 Hours</option>
            <option value={168}>Last 7 Days</option>
          </select>
        </div>
      </div>

      {/* Metrics Grid */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl text-center space-y-2">
            <div className="text-3xl font-black text-white font-mono">{metrics.total_spans || 0}</div>
            <div className="text-xs font-mono font-bold text-slate-400 uppercase">Total Spans</div>
          </Card>
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl text-center space-y-2">
            <div className="text-3xl font-black text-rose-400 font-mono">{metrics.total_errors || 0}</div>
            <div className="text-xs font-mono font-bold text-slate-400 uppercase">Errors Recorded</div>
          </Card>
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl text-center space-y-2">
            <div className="text-3xl font-black text-amber-400 font-mono">{((metrics.error_rate || 0) * 100).toFixed(2)}%</div>
            <div className="text-xs font-mono font-bold text-slate-400 uppercase">Error Rate</div>
          </Card>
          <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl text-center space-y-2">
            <div className="text-3xl font-black text-[#0066FF] font-mono">{Math.round(metrics.avg_duration_ms || 0)} <span className="text-xs font-normal">ms</span></div>
            <div className="text-xs font-mono font-bold text-slate-400 uppercase">Avg Duration</div>
          </Card>
        </div>
      )}

      {/* Services Breakout Card */}
      {metrics?.services && Object.keys(metrics.services).length > 0 && (
        <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
          <div className="flex items-center gap-2 pb-4 border-b border-[#1E293B]">
            <Layers className="w-5 h-5 text-[#0066FF]" />
            <h2 className="font-bold text-lg text-white">Metrics by Microservice Engine</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
            {Object.entries(metrics.services).map(([name, data]: [string, any]) => (
              <div key={name} className="p-4 rounded-xl bg-[#090D16] border border-[#1E293B] space-y-2">
                <div className="font-bold text-white text-sm">{name}</div>
                <div className="flex justify-between text-slate-400"><span>Spans:</span><span className="text-white font-bold">{data.spans}</span></div>
                <div className="flex justify-between text-slate-400"><span>Errors:</span><span className="text-rose-400 font-bold">{data.errors}</span></div>
                <div className="flex justify-between text-slate-400"><span>Avg Duration:</span><span className="text-[#0066FF] font-bold">{data.avg_duration_ms}ms</span></div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Live Spans Log Table */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-[#0066FF] animate-pulse" />
            <h2 className="font-bold text-lg text-white">Live Telemetry Span Stream</h2>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-[#1E293B] px-3 py-1 rounded-full">
            Top {allSpans.length} Spans
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-[#1E293B] text-left text-slate-400 uppercase tracking-wider">
                <th className="pb-3 font-bold">Service</th>
                <th className="pb-3 font-bold">Operation</th>
                <th className="pb-3 font-bold">Status</th>
                <th className="pb-3 font-bold">Duration</th>
                <th className="pb-3 font-bold">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B]/60">
              {allSpans.map((s) => (
                <tr key={s.id} className="hover:bg-[#090D16]/50 transition-colors">
                  <td className="py-3 font-bold text-white">{s.service}</td>
                  <td className="py-3 text-slate-300">{s.operation}</td>
                  <td className="py-3">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      s.status === "ok" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                    }`}>
                      {s.status}
                    </span>
                  </td>
                  <td className="py-3 text-slate-400">
                    {s.attributes?.duration_ms ? `${Math.round(s.attributes.duration_ms)}ms` : "—"}
                  </td>
                  <td className="py-3 text-slate-500">{s.created_at?.slice(0, 19)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
