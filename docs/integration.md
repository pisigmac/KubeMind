# KubeMind Integration Guide: OpenDesk (Identity) & PayDeck (Billing)

This document provides the authoritative integration architecture and configuration guide for connecting **KubeMind** with the shared **OpenDesk** (Identity / Auth Microservice) and **PayDeck** (Razorpay Billing Microservice).

---

## 1. Microservices Topology

```
                                  ┌────────────────────────────────────────┐
                                  │            OpenDesk Service            │
                                  │   Identity, RS256 JWTs & JWKS (.json)  │
                                  │           (Port :8090 / Auth)          │
                                  └────────────────────────────────────────┘
                                                       ▲
                                                       │ JWKS Public Key Fetch
                                                       ▼
┌─────────────────────────┐  HTTP API Req  ┌────────────────────────────────────────┐
│     Client App / SDK    │ ─────────────> │            KubeMind Gateway            │
│  (Next.js / Python / TS)│ <───────────── │   Router (:9080) + Sentinel (:9083)    │
└─────────────────────────┘  Token / Route └────────────────────────────────────────┘
             │                                         │
             │ Checkout Order / Upgrade                │ Metered Token Analytics
             ▼                                         ▼
┌─────────────────────────┐  Verify HMAC   ┌────────────────────────────────────────┐
│     PayDeck Service     │ <───────────── │            KubeMind Control DB         │
│  Razorpay Billing Engine│                │   CFO Cost Aggregation & Metering      │
│  (Port :8787 / Billing) │                └────────────────────────────────────────┘
└─────────────────────────┘
```

---

## 2. Identity & Authentication Integration (OpenDesk / DeskAuth)

**OpenDesk Source Directory:** `/home/oh20210736-ud/Documents/WorkSpace/OpenDesk`  
**Protocol:** OAuth 2.0 / OIDC + RS256 Signed JWTs with Public JWKS  

### 2.1 Authentication Flow
1. User logs in via OpenDesk API (`POST http://localhost:8090/v1/auth/login` or OAuth start URL).
2. OpenDesk issues an RS256-signed Bearer JWT containing user identity and organization claims.
3. KubeMind microservices (Router `:9080`, Mind `:9081`, Sentinel `:9083`) validate incoming JWTs against OpenDesk's public JWKS (`http://localhost:8090/.well-known/jwks.json`).
4. Validation occurs **entirely in-memory** inside KubeMind via cached public keys (zero network call per request).

### 2.2 JWT Claims Specification

OpenDesk embeds product grants specifically for KubeMind:

```json
{
  "sub": "usr_99a8b123-4567-89ab-cdef",
  "email": "cfo@acmecorp.com",
  "org_id": "org_acme_corp",
  "workspace_id": "acme_prod",
  "aud": ["kubemind"],
  "roles": {
    "kubemind": "admin"
  },
  "iss": "https://auth.opendesk.local",
  "exp": 1787500000
}
```

### 2.3 Role & Scope Mapping in KubeMind

KubeMind's RBAC engine (`shared/python/kubemind_auth/`) extracts `roles.kubemind` and applies permissions:

| OpenDesk Role | KubeMind Permission Scopes | Endpoint Access |
| :--- | :--- | :--- |
| `"admin"` | `*`, `usage:org`, `audit:admin` | Full access, CFO Org Analytics, Cryptographic Ledger Admin |
| `"developer"` | `chat`, `route`, `classify`, `mind:query`, `mind:ingest`, `audit:read`, `usage:read` | Prompt routing, vector knowledge query/ingest, usage read |
| `"auditor"` | `audit:read`, `audit:verify`, `usage:read` | Cryptographic ledger verification, audit log inspection |
| `"viewer"` | `metrics:read`, `dashboard:read`, `usage:read` | Dashboard monitoring, Prometheus metrics |

---

## 3. Billing & Payment Integration (PayDeck / DeskBill)

**PayDeck Source Directory:** `/home/oh20210736-ud/Documents/WorkSpace/PayDeck`  
**Protocol:** REST API + HMAC Signature Verification + Razorpay Checkout  

### 3.1 Product & Plan Bootstrap
KubeMind registers under product slug `kubemind` with product API key (`pd_live_...` / `pd_test_...`):

```bash
# 1. Register KubeMind product in PayDeck
curl -s -X POST "http://localhost:8787/v1/admin/products" \
  -H "X-Admin-Token: $BILLING_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "kubemind",
    "name": "KubeMind AI Governance Gateway",
    "rate_limit_per_hour": 1000
  }'

# 2. Generate Product API Key
curl -s -X POST "http://localhost:8787/v1/admin/products/kubemind/keys" \
  -H "X-Admin-Token: $BILLING_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "production", "environment": "live"}'
# -> Returns {"key": "pd_live_..."}

# 3. Create Subscription Plans
curl -s -X POST "http://localhost:8787/v1/admin/products/kubemind/plans" \
  -H "X-Admin-Token: $BILLING_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "pro",
    "name": "KubeMind Pro Plan",
    "amount_paise": 399900,
    "currency": "INR",
    "interval": "month"
  }'
```

### 3.2 Order Creation & Payment Verification Flow

1. **User clicks "Upgrade Plan" in KubeMind Dashboard (`/dashboard`)**:
   Dashboard calls PayDeck to create a Razorpay order:
   ```bash
   curl -s -X POST "http://localhost:8787/v1/orders" \
     -H "Authorization: Bearer pd_live_..." \
     -H "Idempotency-Key: order-acme-prod-001" \
     -H "Content-Type: application/json" \
     -d '{"plan": "pro"}'
   ```
   *PayDeck returns `{ "order_id": "order_123", "key_id": "rzp_live_...", "amount": 399900 }`.*

2. **Browser Opens Razorpay Checkout Modal**:
   The dashboard renders the Checkout modal using returned `order_id` and `key_id`.

3. **Signature Verification (`POST /v1/verify`)**:
   Upon payment success, Dashboard passes the Razorpay payload to PayDeck for HMAC verification:
   ```bash
   curl -s -X POST "http://localhost:8787/v1/verify" \
     -H "Authorization: Bearer pd_live_..." \
     -H "Content-Type: application/json" \
     -d '{
       "razorpay_order_id": "order_123",
       "razorpay_payment_id": "pay_456",
       "razorpay_signature": "a1b2c3..."
     }'
   ```

4. **Token Usage Metering Sync**:
   KubeMind Router's [`/v1/usage/org-analytics`](file:///home/oh20210736-ud/Documents/WorkSpace/kubemind/services/router/src/router/usage.py) aggregates total tokens routed across workspaces. When plan limits are reached, KubeMind automatically initiates top-up orders through PayDeck.

---

## 4. Environment Configuration Reference

### KubeMind Router / Services (`.env`)

```bash
# Identity (OpenDesk) Integration
KUBEMIND_AUTH_REQUIRED=true
AUTH_SERVICE_URL=http://localhost:8090
AUTH_JWKS_URL=http://localhost:8090/.well-known/jwks.json

# Billing (PayDeck) Integration
PAYDECK_SERVICE_URL=http://localhost:8787
PAYDECK_API_KEY=pd_live_kubemind_prod_key_123
```

### Local Dev Verification
During local dev, set `ALLOW_DEV_CHARGE=1` in PayDeck to test checkout flows without requiring real Razorpay credentials.
