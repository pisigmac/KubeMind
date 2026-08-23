export interface KubeMindClientConfig {
  apiKey?: string;
  workspaceId?: string;
  routerUrl?: string;
  mindUrl?: string;
  sentinelUrl?: string;
  timeoutMs?: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  name?: string;
}

export interface RoutingDecision {
  reason_code?: string;
  intent?: string;
  profile?: string;
  considered_providers?: string[];
  eligible_providers?: string[];
  selected_provider?: string;
  retrieval_status?: string | null;
  retrieval_hits?: number;
  distance?: number;
}

export interface ChatCompletionParams {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  stream?: boolean;
  tools?: Record<string, any>[];
  preferred_target?: string;
  fallback?: string;
  enable_cache?: boolean;
  policy?: "cost" | "quality" | "latency";
  max_latency_ms?: number;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message?: {
      role: string;
      content: string;
    };
    text?: string;
    finish_reason?: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  provider?: string;
  cached?: boolean;
  cache_hit?: boolean;
  cache_type?: string | null;
  fallback?: boolean;
  latency_ms?: number;
  route_target?: string;
  intent?: string;
  intent_confidence?: number;
  profile?: string;
  policy_action?: string;
  egress_class?: string;
  retrieval_used?: boolean;
  retrieval_status?: string | null;
  routing_decision?: RoutingDecision;
}

export interface RouteParams {
  prompt: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  preferred_target?: string;
  fallback?: string;
  enable_cache?: boolean;
  policy?: "cost" | "quality" | "latency";
  max_latency_ms?: number;
}

export interface RouteResponse {
  content: string;
  latency_ms: number;
  cache_hit: boolean;
  cache_type?: string | null;
  provider?: string;
  route_target?: string;
  intent?: string;
  intent_confidence?: number;
  profile?: string;
  policy_action?: string;
  egress_class?: string;
  retrieval_used: boolean;
  retrieval_status?: string | null;
  routing_decision?: RoutingDecision;
  model?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  distance?: number;
  similarity?: number;
  fallback: boolean;
  raw?: Record<string, any>;
}

export interface ClassificationResponse {
  intent: string;
  confidence: number;
  margin?: number;
  method?: string;
  abstained?: boolean;
  scores?: Record<string, number>;
}

export interface IngestMemoryParams {
  content: string;
  source?: string;
  metadata?: Record<string, any>;
}

export interface IngestMemoryResponse {
  status: string;
  id?: string;
  chunks_created?: number;
}

export interface QueryMemoryParams {
  query: string;
  top_k?: number;
  filters?: Record<string, any>;
}

export interface QueryMemoryResponse {
  results?: Array<{
    id?: string;
    content?: string;
    source?: string;
    score?: number;
    metadata?: Record<string, any>;
  }>;
  nodes?: Array<any>;
}

export interface VerifyAuditLedgerParams {
  limit?: number;
}

export interface AuditLedgerResponse {
  status: string;
  verified: boolean;
  total_entries?: number;
  head_hash?: string;
  entries?: Array<{
    id: number;
    workspace_id: string;
    chain_seq: number;
    entry_hash: string;
    prev_hash: string;
    timestamp: string;
    event_type: string;
    payload: Record<string, any>;
  }>;
}

export interface CostAnalyticsResponse {
  workspace_id: string;
  window_hours: number;
  total_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_spend_usd: number;
  providers: Record<string, { requests: number; tokens: number; spend_usd: number }>;
  models: Record<string, { requests: number; tokens: number; spend_usd: number }>;
}

