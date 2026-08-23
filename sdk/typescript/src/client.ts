import {
  AuditLedgerResponse,
  ChatCompletionParams,
  ChatCompletionResponse,
  ClassificationResponse,
  CostAnalyticsResponse,
  IngestMemoryParams,
  IngestMemoryResponse,
  KubeMindClientConfig,
  QueryMemoryParams,
  QueryMemoryResponse,
  RouteParams,
  RouteResponse,
  VerifyAuditLedgerParams,
} from "./types";

export class KubeMindError extends Error {
  public status: number;
  public details?: any;

  constructor(message: string, status: number, details?: any) {
    super(message);
    this.name = "KubeMindError";
    this.status = status;
    this.details = details;
  }
}

export class KubeMindClient {
  private apiKey?: string;
  private workspaceId: string;
  private routerUrl: string;
  private mindUrl: string;
  private sentinelUrl: string;
  private timeoutMs: number;

  constructor(config: KubeMindClientConfig = {}) {
    this.apiKey = config.apiKey;
    this.workspaceId = config.workspaceId || "default";
    this.routerUrl = (config.routerUrl || "http://localhost:9080").replace(/\/+$/, "");
    this.mindUrl = (config.mindUrl || "http://localhost:9081").replace(/\/+$/, "");
    this.sentinelUrl = (config.sentinelUrl || "http://localhost:9083").replace(/\/+$/, "");
    this.timeoutMs = config.timeoutMs || 30000;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Workspace-ID": this.workspaceId,
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  private async request<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          ...this.getHeaders(),
          ...(options.headers || {}),
        },
      });

      if (!response.ok) {
        let errorBody: any;
        try {
          errorBody = await response.json();
        } catch {
          errorBody = await response.text();
        }
        throw new KubeMindError(
          `Request to ${url} failed with status ${response.status}: ${
            typeof errorBody === "object" ? JSON.stringify(errorBody) : errorBody
          }`,
          response.status,
          errorBody
        );
      }

      return (await response.json()) as T;
    } catch (err: any) {
      if (err.name === "AbortError") {
        throw new KubeMindError(
          `Request to ${url} timed out after ${this.timeoutMs}ms`,
          408
        );
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Dispatch a chat completion prompt to KubeMind router for intent classification,
   * inline pre-dispatch sensitivity gating, memory augmentation, and model dispatch.
   */
  public async chatCompletion(
    params: ChatCompletionParams
  ): Promise<ChatCompletionResponse> {
    const url = `${this.routerUrl}/v1/chat/completions`;
    return this.request<ChatCompletionResponse>(url, {
      method: "POST",
      body: JSON.stringify({
        enable_cache: true,
        ...params,
      }),
    });
  }

  /**
   * Stream chat completion SSE events with real-time de-anonymization applied.
   */
  public async *chatStream(
    params: ChatCompletionParams
  ): AsyncIterable<any> {
    const url = `${this.routerUrl}/v1/chat/completions`;
    const response = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        ...params,
        stream: true,
      }),
    });

    if (!response.ok) {
      throw new KubeMindError(`Streaming failed: HTTP ${response.status}`, response.status);
    }

    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ") && !trimmed.startsWith("data: [DONE]")) {
          try {
            yield JSON.parse(trimmed.slice(6));
          } catch {
            // Ignore parse errors on partial chunks
          }
        }
      }
    }
  }

  /**
   * Dispatch a simplified semantic prompt route request to KubeMind router.
   */
  public async route(params: RouteParams): Promise<RouteResponse> {
    const url = `${this.routerUrl}/v1/route`;
    return this.request<RouteResponse>(url, {
      method: "POST",
      body: JSON.stringify({
        enable_cache: true,
        ...params,
      }),
    });
  }

  /**
   * Dry-run classify a prompt for intent and sensitivity without calling external providers.
   */
  public async classify(prompt: string): Promise<ClassificationResponse> {
    const url = `${this.routerUrl}/v1/classify`;
    return this.request<ClassificationResponse>(url, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });
  }

  /**
   * Ingest text knowledge or document chunks into the tenant-scoped Mind knowledge graph.
   */
  public async ingestMemory(
    params: IngestMemoryParams
  ): Promise<IngestMemoryResponse> {
    const url = `${this.mindUrl}/v1/ingest`;
    return this.request<IngestMemoryResponse>(url, {
      method: "POST",
      body: JSON.stringify({
        source: "sdk/typescript",
        metadata: {},
        ...params,
      }),
    });
  }

  /**
   * Query the tenant-scoped Mind knowledge graph using hybrid vector + keyword search.
   */
  public async queryMemory(
    params: QueryMemoryParams
  ): Promise<QueryMemoryResponse> {
    const url = `${this.mindUrl}/v1/query`;
    return this.request<QueryMemoryResponse>(url, {
      method: "POST",
      body: JSON.stringify({
        top_k: 4,
        filters: {},
        ...params,
      }),
    });
  }

  /**
   * Cryptographically verify and fetch the SHA-256 hash-chained audit ledger from Sentinel.
   */
  public async verifyAuditLedger(
    params: VerifyAuditLedgerParams = {}
  ): Promise<AuditLedgerResponse> {
    const limit = params.limit || 50;
    const url = `${this.sentinelUrl}/v1/audit/verify?workspace_id=${encodeURIComponent(
      this.workspaceId
    )}&limit=${limit}`;
    return this.request<AuditLedgerResponse>(url, {
      method: "GET",
    });
  }

  /**
   * Fetch CFO-level aggregated cost, token and usage analytics for the workspace.
   */
  public async getCostAnalytics(
    windowHours: number = 24
  ): Promise<CostAnalyticsResponse> {
    const url = `${this.routerUrl}/v1/usage/analytics?window_hours=${windowHours}`;
    return this.request<CostAnalyticsResponse>(url, {
      method: "GET",
    });
  }
}
