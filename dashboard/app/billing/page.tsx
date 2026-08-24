"use client";

import { useState, useEffect } from "react";
import {
  fetchPlans,
  createOrder,
  verifyPayment,
  formatINR,
  type PayDeckPlan,
} from "@/lib/paydeck";

declare global {
  interface Window {
    Razorpay: new (opts: Record<string, unknown>) => {
      open: () => void;
    };
  }
}

function CheckIcon() {
  return (
    <svg className="w-5 h-5 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

const PLAN_FEATURES: Record<string, string[]> = {
  free: [
    "100K tokens / month",
    "1 Workspace",
    "Regex PII detection",
    "Standard Routing",
    "Community support",
  ],
  pro: [
    "10M tokens / month",
    "5 Workspaces",
    "Semantic Caching (30–60% LLM savings)",
    "ONNX NER Privacy Engine",
    "30-day CFO Analytics",
    "Email Support",
  ],
  growth: [
    "50M tokens / month",
    "20 Workspaces",
    "Full Mind Vector RAG Ingestion",
    "SHA-256 Cryptographic Audit Ledger",
    "Cross-Workspace Org Analytics",
    "Priority Support",
  ],
};

export default function BillingPage() {
  const [plans, setPlans] = useState<PayDeckPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [currentPlan] = useState("free");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchPlans().then((p) => {
      setPlans(p);
      setLoading(false);
    });
  }, []);

  const handleUpgrade = async (plan: PayDeckPlan) => {
    if (plan.slug === "free" || plan.slug === currentPlan) return;
    setUpgrading(plan.slug);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const idempotencyKey = `kubemind-${plan.slug}-${Date.now()}`;
      const order = await createOrder(plan.slug, idempotencyKey);

      if (!order.key_id || order.key_id === "") {
        // Dev mode — PayDeck issued a fake paid order
        setSuccessMsg(`✅ Dev mode: ${plan.name} plan activated (no real charge)`);
        setUpgrading(null);
        return;
      }

      // Load Razorpay Checkout SDK dynamically
      await new Promise<void>((resolve, reject) => {
        if (window.Razorpay) return resolve();
        const script = document.createElement("script");
        script.src = "https://checkout.razorpay.com/v1/checkout.js";
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Failed to load Razorpay SDK"));
        document.body.appendChild(script);
      });

      const rzp = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency || "INR",
        name: "KubeMind",
        description: `${plan.name} Subscription`,
        order_id: order.order_id,
        handler: async (response: {
          razorpay_order_id: string;
          razorpay_payment_id: string;
          razorpay_signature: string;
        }) => {
          try {
            const verified = await verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            if (verified.paid) {
              setSuccessMsg(`✅ Payment successful! ${plan.name} plan is now active.`);
            } else {
              setErrorMsg("Payment verification failed. Contact support.");
            }
          } catch {
            setErrorMsg("Payment verification error. Contact support.");
          }
          setUpgrading(null);
        },
        modal: {
          ondismiss: () => setUpgrading(null),
        },
        theme: { color: "#6366f1" },
      });

      rzp.open();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Checkout failed");
      setUpgrading(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-white p-8">
      {/* Header */}
      <div className="max-w-5xl mx-auto mb-12 text-center">
        <h1 className="text-4xl font-bold mb-3 bg-gradient-to-r from-indigo-400 to-emerald-400 bg-clip-text text-transparent">
          KubeMind Plans
        </h1>
        <p className="text-slate-400 text-lg">
          Upgrade your AI governance gateway. Cancel anytime.
        </p>
      </div>

      {/* Status messages */}
      {successMsg && (
        <div className="max-w-5xl mx-auto mb-6 p-4 rounded-xl bg-emerald-900/40 border border-emerald-700 text-emerald-300 text-sm">
          {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="max-w-5xl mx-auto mb-6 p-4 rounded-xl bg-red-900/40 border border-red-700 text-red-300 text-sm">
          {errorMsg}
        </div>
      )}

      {/* Plan Cards */}
      {loading ? (
        <div className="max-w-5xl mx-auto text-center text-slate-500 py-20">
          Loading plans…
        </div>
      ) : (
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrent = plan.slug === currentPlan;
            const isPro = plan.slug === "pro";
            const features = PLAN_FEATURES[plan.slug] ?? [];
            const isUpgrading = upgrading === plan.slug;

            return (
              <div
                key={plan.slug}
                className={`relative rounded-2xl border p-6 flex flex-col gap-5 transition-all ${
                  isPro
                    ? "border-indigo-500 bg-indigo-950/40 shadow-lg shadow-indigo-900/30"
                    : "border-slate-700/60 bg-slate-900/60"
                }`}
              >
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 text-xs font-semibold bg-indigo-500 rounded-full">
                    Most Popular
                  </div>
                )}
                {isCurrent && (
                  <div className="absolute -top-3 right-4 px-3 py-1 text-xs font-semibold bg-slate-600 rounded-full">
                    Current Plan
                  </div>
                )}

                <div>
                  <h2 className="text-xl font-bold mb-1">{plan.name}</h2>
                  <p className="text-3xl font-extrabold">
                    {formatINR(plan.amount_paise)}
                    {plan.amount_paise > 0 && (
                      <span className="text-base font-normal text-slate-400"> /mo</span>
                    )}
                  </p>
                  {plan.description && (
                    <p className="text-slate-400 text-sm mt-2">{plan.description}</p>
                  )}
                </div>

                <ul className="flex flex-col gap-2 flex-1">
                  {features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                      <CheckIcon />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleUpgrade(plan)}
                  disabled={isCurrent || isUpgrading || !!upgrading}
                  className={`w-full py-3 rounded-xl font-semibold text-sm transition-all ${
                    isCurrent
                      ? "bg-slate-700 text-slate-400 cursor-default"
                      : isPro
                      ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-900/40"
                      : "bg-slate-700 hover:bg-slate-600 text-white"
                  } disabled:opacity-50`}
                >
                  {isUpgrading
                    ? "Processing…"
                    : isCurrent
                    ? "Current Plan"
                    : plan.slug === "free"
                    ? "Downgrade"
                    : `Upgrade to ${plan.name}`}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Enterprise CTA */}
      <div className="max-w-5xl mx-auto mt-10 rounded-2xl border border-slate-700/60 bg-slate-900/60 p-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold mb-1">Enterprise Air-Gapped / Self-Hosted</h3>
          <p className="text-slate-400 text-sm">
            Unlimited vCPUs · 100% Offline · SOC 2 / HIPAA Audit Package · 24/7 SLA
          </p>
        </div>
        <a
          href="mailto:enterprise@kubemind.ai?subject=Enterprise%20License%20Inquiry"
          className="shrink-0 px-6 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-semibold text-sm transition-all"
        >
          Contact Sales →
        </a>
      </div>
    </div>
  );
}
