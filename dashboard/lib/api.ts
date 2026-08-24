"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function apiFetch(path: string, options?: RequestInit) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-ID": "default",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const routerApi = {
  health: () => apiFetch("/api/router/health"),
  providers: () => apiFetch("/api/router/v1/providers/health"),
  usage: () => apiFetch("/api/router/v1/usage"),
  analytics: (windowHours = 24) => apiFetch(`/api/router/v1/usage/analytics?window_hours=${windowHours}`),
  orgAnalytics: (windowHours = 720) => apiFetch(`/api/router/v1/usage/org-analytics?window_hours=${windowHours}`),
  cacheStats: () => apiFetch("/api/router/v1/cache/stats"),
};

export const mindApi = {
  health: () => apiFetch("/api/mind/health"),
  query: (q: string, filters?: Record<string, string>) =>
    apiFetch("/api/mind/v1/query", {
      method: "POST",
      body: JSON.stringify({ query: q, filters, top_k: 10 }),
    }),
  ingest: (source: string, type: string = "document") =>
    apiFetch("/api/mind/v1/ingest", {
      method: "POST",
      body: JSON.stringify({ source, type }),
    }),
  graph: () => apiFetch("/api/mind/v1/graph"),
};

export const agentsApi = {
  health: () => apiFetch("/api/agents/health"),
  missions: (limit = 50) => apiFetch(`/api/agents/v1/missions?limit=${limit}`),
  createMission: (prompt: string, mode = "sync") =>
    apiFetch("/api/agents/v1/missions", {
      method: "POST",
      body: JSON.stringify({ prompt, mode }),
    }),
  getMission: (id: string) => apiFetch(`/api/agents/v1/missions/${id}`),
  tools: () => apiFetch("/api/agents/v1/tools"),
};

export const sentinelApi = {
  health: () => apiFetch("/api/sentinel/health"),
  spans: (workspace = "default", limit = 100) =>
    apiFetch(`/api/sentinel/v1/spans?workspace_id=${workspace}&limit=${limit}`),
  metrics: (workspace = "default", hours = 24) =>
    apiFetch(`/api/sentinel/v1/metrics?workspace_id=${workspace}&hours=${hours}`),
  stats: () => apiFetch("/api/sentinel/v1/stats"),
  verifyAudit: (workspace = "default", limit = 50) =>
    apiFetch(`/api/sentinel/v1/audit/verify?workspace_id=${workspace}&limit=${limit}`),
};

