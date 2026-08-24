/**
 * PayDeck billing client for KubeMind Dashboard
 *
 * Connects to the PayDeck Razorpay billing microservice.
 * KubeMind never stores Razorpay secrets — PayDeck owns order state,
 * signature verification, webhooks, and payment logs.
 *
 * Env vars:
 *   NEXT_PUBLIC_PAYDECK_URL  — PayDeck base URL (default: http://localhost:8787)
 *   PAYDECK_API_KEY          — Product API key (pd_live_... / pd_test_...) set server-side
 */

export const PAYDECK_URL =
  process.env.NEXT_PUBLIC_PAYDECK_URL || "http://localhost:8787";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PayDeckPlan {
  slug: string;
  name: string;
  amount_paise: number;
  currency: string;
  interval: "month" | "year" | "one_time";
  description?: string;
}

export interface PayDeckOrderResponse {
  order_id: string;
  key_id: string;
  amount: number;
  currency: string;
  plan: string;
  idempotency_key: string;
}

export interface PayDeckVerifyRequest {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface PayDeckVerifyResponse {
  paid: boolean;
  payment_id: string;
  order_id: string;
  plan?: string;
  paid_at?: string;
}

// ─── KubeMind Plans ───────────────────────────────────────────────────────────

export const KUBEMIND_PLANS: PayDeckPlan[] = [
  {
    slug: "free",
    name: "Developer",
    amount_paise: 0,
    currency: "INR",
    interval: "month",
    description: "100K tokens/mo · 1 Workspace · Community support",
  },
  {
    slug: "pro",
    name: "Pro / Team",
    amount_paise: 399900,
    currency: "INR",
    interval: "month",
    description: "10M tokens/mo · 5 Workspaces · Semantic Cache · CFO Analytics",
  },
  {
    slug: "growth",
    name: "Growth",
    amount_paise: 2049900,
    currency: "INR",
    interval: "month",
    description: "50M tokens/mo · 20 Workspaces · Full Mind RAG · Priority support",
  },
];

// ─── Client ───────────────────────────────────────────────────────────────────

async function paydeck<T>(
  path: string,
  options?: RequestInit,
  apiKey?: string
): Promise<T> {
  const key =
    apiKey ||
    process.env.PAYDECK_API_KEY ||
    process.env.NEXT_PUBLIC_PAYDECK_API_KEY ||
    "";

  const res = await fetch(`${PAYDECK_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`PayDeck HTTP ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

/**
 * Fetch available KubeMind billing plans from PayDeck.
 */
export async function fetchPlans(apiKey?: string): Promise<PayDeckPlan[]> {
  try {
    const data = await paydeck<{ plans: PayDeckPlan[] }>(
      "/v1/products/kubemind/plans",
      { method: "GET" },
      apiKey
    );
    return data.plans ?? KUBEMIND_PLANS;
  } catch {
    // Fall back to hardcoded plans if PayDeck is unreachable (local dev)
    return KUBEMIND_PLANS;
  }
}

/**
 * Create a Razorpay order for a KubeMind plan.
 * Returns order_id + key_id to pass to the Razorpay Checkout SDK.
 */
export async function createOrder(
  planSlug: string,
  idempotencyKey: string,
  apiKey?: string
): Promise<PayDeckOrderResponse> {
  return paydeck<PayDeckOrderResponse>(
    "/v1/orders",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ plan: planSlug }),
    },
    apiKey
  );
}

/**
 * Verify HMAC payment signature after Razorpay Checkout success callback.
 * PayDeck verifies the signature and marks the order as paid.
 */
export async function verifyPayment(
  payload: PayDeckVerifyRequest,
  apiKey?: string
): Promise<PayDeckVerifyResponse> {
  return paydeck<PayDeckVerifyResponse>(
    "/v1/verify",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    apiKey
  );
}

/**
 * Utility: format paise to INR string.
 * e.g. 399900 → "₹3,999"
 */
export function formatINR(paise: number): string {
  if (paise === 0) return "Free";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);
}
