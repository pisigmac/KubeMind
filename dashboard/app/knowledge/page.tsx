"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { mindApi } from "@/lib/api";
import { Database, Search, Upload, FileText, Loader2, Sparkles, FolderPlus, Layers } from "lucide-react";

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [graphData, setGraphData] = useState<any>(null);

  async function loadGraph() {
    try {
      const data = await mindApi.graph();
      setGraphData(data);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadGraph();
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await mindApi.query(query);
      setResults(data.results || []);
    } catch (err: any) {
      alert("Search failed: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!source.trim()) return;
    setIngesting(true);
    try {
      const data = await mindApi.ingest(source);
      alert(`Ingested ${data.ingested} nodes`);
      setSource("");
      await loadGraph();
    } catch (err: any) {
      alert("Ingest failed: " + err.message);
    } finally {
      setIngesting(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIngesting(true);
    try {
      const text = await file.text();
      const res = await fetch("/api/mind/v1/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Workspace-ID": "default",
        },
        body: JSON.stringify({ source: file.name, type: "document", content: text }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      alert(`Successfully uploaded and ingested "${file.name}" (${data.ingested} node)`);
      await loadGraph();
    } catch (err: any) {
      alert("File upload failed: " + err.message);
    } finally {
      setIngesting(false);
      e.target.value = "";
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-8 rounded-3xl bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0066FF]/10 border border-[#0066FF]/30 text-[#0066FF] text-xs font-mono font-bold">
            <Database className="w-3.5 h-3.5" />
            <span>Hybrid Context Graph</span>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Mind Knowledge Base</h1>
          <p className="text-slate-400 text-sm max-w-xl">
            Hybrid vector embeddings + BM25 keyword RAG search stored natively in PostgreSQL.
          </p>
        </div>
      </div>

      {/* Ingest & File Upload Card */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
        <div className="flex items-center justify-between font-mono text-xs text-slate-400">
          <span className="flex items-center gap-2">
            <FolderPlus className="w-4 h-4 text-[#0066FF]" />
            Ingest Knowledge Sources
          </span>
          <span className="text-emerald-400 font-bold">PostgreSQL Vector Store</span>
        </div>

        <div className="flex flex-col md:flex-row gap-3">
          <form onSubmit={handleIngest} className="flex-1 flex gap-2">
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Enter URL or file path (e.g. Dockerfile, Makefile)..."
              className="flex-1 px-4 py-3 border border-[#1E293B] rounded-xl bg-[#090D16] text-white text-sm focus:outline-none focus:border-[#0066FF] transition-all font-sans"
            />
            <button type="submit" className="btn-secondary whitespace-nowrap" disabled={ingesting}>
              {ingesting ? "Ingesting..." : "Ingest Source"}
            </button>
          </form>

          <label className="btn-primary flex items-center justify-center gap-2 cursor-pointer whitespace-nowrap">
            <Upload className="w-4 h-4" />
            <span>{ingesting ? "Uploading..." : "Upload Local File"}</span>
            <input type="file" onChange={handleFileUpload} className="hidden" disabled={ingesting} />
          </label>
        </div>
      </Card>

      {/* Search Input Card */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-4 top-4" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search hybrid vector graph with natural language queries..."
              className="w-full pl-11 pr-4 py-3 border border-[#1E293B] rounded-xl bg-[#090D16] text-white text-sm focus:outline-none focus:border-[#0066FF] transition-all font-sans"
            />
          </div>
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            <span>{loading ? "Searching..." : "Vector Search"}</span>
          </button>
        </form>
      </Card>

      {/* Search Results View */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2 font-mono">
            <span>Hybrid Search Results</span>
            <span className="text-xs font-normal text-[#0066FF] bg-[#0066FF]/10 px-2.5 py-0.5 rounded-full border border-[#0066FF]/30">
              {results.length} Matches
            </span>
          </h2>
          <div className="space-y-3">
            {results.map((r) => (
              <Card key={r.id} className="p-6 bg-[#0F172A] border border-[#1E293B] space-y-2">
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="px-2.5 py-1 bg-[#0066FF]/15 border border-[#0066FF]/30 text-[#0066FF] rounded-lg font-bold">
                    {r.type}
                  </span>
                  <span className="text-emerald-400 font-bold">Relevance Score: {r.score?.toFixed(3)}</span>
                </div>
                <p className="text-sm font-mono text-slate-200 bg-[#090D16] p-4 rounded-xl border border-[#1E293B] whitespace-pre-wrap leading-relaxed">
                  {r.content}
                </p>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Graph Node Explorer View */}
      <Card className="p-6 bg-[#0F172A] border border-[#1E293B] shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-[#0066FF]" />
            <h2 className="font-bold text-lg text-white">Ingested Knowledge Graph Nodes</h2>
          </div>
          <span className="text-xs font-mono font-bold text-slate-400 bg-[#1E293B] px-3 py-1 rounded-full">
            {graphData?.node_count || 0} Total Nodes
          </span>
        </div>

        {graphData && graphData.nodes && graphData.nodes.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {graphData.nodes.map((node: any) => (
              <div key={node.id} className="p-4 rounded-xl bg-[#090D16] border border-[#1E293B] space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="font-bold text-white truncate max-w-[200px]">
                    {node.metadata?.filename || node.metadata?.path || "Ingested Document"}
                  </span>
                  <span className="px-2 py-0.5 bg-[#1E293B] border border-[#334155] rounded text-slate-300">
                    {node.type}
                  </span>
                </div>
                <div className="font-mono text-xs text-slate-500 truncate">ID: {node.id}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-slate-500 font-mono">
            No knowledge nodes ingested yet. Click 'Upload Local File' above to ingest documents.
          </div>
        )}
      </Card>
    </div>
  );
}
