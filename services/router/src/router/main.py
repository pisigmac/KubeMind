import os
import time
import uuid
import hashlib
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List, Tuple

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from router.models import (
    ChatRequest,
    EmbeddingsRequest,
    RouteRequest,
    RouteResponse,
    DecisionRecord,
    Message,
)
from router.providers import ProviderRegistry
from router.cache import CacheManager, SemanticCache
from router.cache.semantic import signature as cache_signature
from router.ratelimit import RateLimiter
from router.usage import UsageTracker
from router.tracer import TracerClient
from router.mind_client import MindClient
from router.intent import (
    IntentClassifier,
    IntentResult,
    extract_user_text,
    select_classification_text,
)
from router.policy import Action, PolicyEngine, PolicyError, PolicyVerdict
from router.profiles import ProfileRegistry, RouteProfile
from router.auth import API_KEY_HEADER, WORKSPACE_HEADER, AuthError, Authenticator
from router import metrics as router_metrics

# ── Global state ─────────────────────────────────────────────────
registry: Optional[ProviderRegistry] = None
cache: Optional[CacheManager] = None
semantic_cache: Optional[SemanticCache] = None
rate_limiter: Optional[RateLimiter] = None
usage_tracker: Optional[UsageTracker] = None
sentinel_client: Optional[TracerClient] = None
mind_client: Optional[MindClient] = None
classifier: Optional[IntentClassifier] = None
policy_engine: Optional[PolicyEngine] = None
profiles: Optional[ProfileRegistry] = None
authenticator: Optional[Authenticator] = None
cache_ttl: int = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    global registry, cache, semantic_cache, rate_limiter, usage_tracker
    global sentinel_client, mind_client, classifier, policy_engine, profiles
    global authenticator, cache_ttl

    cache = CacheManager()
    await cache.connect()

    rate_limiter = RateLimiter(redis_client=cache.client)

    usage_tracker = UsageTracker()
    await usage_tracker.init()

    sentinel_client = TracerClient()
    await sentinel_client.init()

    registry = ProviderRegistry(cache=cache, usage_tracker=usage_tracker)
    await registry.load_providers()

    cache_ttl = int(registry.config.get("cache", {}).get("ttl_seconds", 300))
    semantic_cache = SemanticCache.from_config(registry.config, redis_client=cache.client)
    semantic_cache.bind_redis(cache.client)

    profiles = ProfileRegistry.from_config(registry.config)
    policy_engine = PolicyEngine.from_config(registry.config)
    authenticator = Authenticator.from_config(registry.config)
    print(authenticator.startup_banner())

    mind_client = MindClient()
    await mind_client.init()

    classifier = IntentClassifier.from_config(registry.config)
    indexed = await classifier.build_index(semantic_cache.embed)
    print(
        f"[router] intent classifier: {len(classifier.intents)} intents, "
        f"{indexed} examples indexed, "
        f"{'semantic' if classifier.is_ready else 'rules-only'} mode"
    )

    print("[router] Initialized")
    yield

    await cache.disconnect()
    if semantic_cache:
        await semantic_cache.close()
    if mind_client:
        await mind_client.close()
    await usage_tracker.close()
    if sentinel_client:
        await sentinel_client.close()
    await registry.close()


app = FastAPI(
    title="KubeMind Router",
    version="0.3.0",
    lifespan=lifespan,
)


def _cors_origins() -> List[str]:
    raw = os.environ.get("KUBEMIND_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://localhost:9000", "http://localhost:3000"]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", API_KEY_HEADER, WORKSPACE_HEADER],
)


# ── Auth dependency ──────────────────────────────────────────────

async def get_auth(request: Request):
    if not authenticator:
        raise HTTPException(status_code=503, detail="Router not initialized")
    try:
        return authenticator.authenticate(
            request.headers.get(API_KEY_HEADER),
            request.headers.get(WORKSPACE_HEADER),
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


async def get_workspace(request: Request) -> str:
    return (await get_auth(request)).workspace_id


async def require_admin(request: Request):
    """Admin operations need a configured key even in open mode."""
    admin_key = os.environ.get("KUBEMIND_ADMIN_KEY", "")
    presented = request.headers.get(API_KEY_HEADER, "")
    if admin_key:
        if presented != admin_key:
            raise HTTPException(status_code=403, detail="Admin key required")
        return
    auth = await get_auth(request)
    if not auth.authenticated:
        raise HTTPException(
            status_code=403,
            detail="Admin operations require KUBEMIND_ADMIN_KEY or an authenticated key",
        )


# ── Helpers ──────────────────────────────────────────────────────

def _cache_bypassed(request: Request, enable_cache: Optional[bool]) -> bool:
    if enable_cache is False:
        return True
    header = request.headers.get("X-KubeMind-Cache", "").lower()
    return header in ("bypass", "false", "0", "no")


def _exact_cache_key(
    prefix: str, model: str, messages: list, temperature: float, tools: list = None
) -> str:
    data = {
        "model": model,
        "messages": [(m.role, m.content) for m in messages],
        "temp": temperature,
    }
    if tools:
        data["tools"] = tools
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return f"km:exact:{prefix}:{digest}"


def _system_prompt(messages: List[Message]) -> str:
    return "\n".join(m.content for m in messages if m.role == "system")


def _enrich(
    response: Dict[str, Any],
    *,
    provider: str,
    fallback: bool,
    cache_hit: bool,
    cache_type: Optional[str],
    latency_ms: float,
    route_target: str,
    intent: str,
    intent_confidence: float = 0.0,
    profile: Optional[str] = None,
    policy_action: str = "allow",
    egress_class: str = "any",
    retrieval_used: bool = False,
    distance: Optional[float] = None,
    similarity: Optional[float] = None,
) -> Dict[str, Any]:
    response["provider"] = provider
    response["fallback"] = fallback
    response["cached"] = cache_hit
    response["cache_hit"] = cache_hit
    response["cache_type"] = cache_type
    response["latency_ms"] = round(latency_ms, 3)
    response["route_target"] = route_target
    response["intent"] = intent
    response["intent_confidence"] = round(intent_confidence, 4)
    response["profile"] = profile
    response["policy_action"] = policy_action
    response["egress_class"] = egress_class
    response["retrieval_used"] = retrieval_used
    if distance is not None:
        response["distance"] = round(distance, 6)
        response["similarity"] = round(
            similarity if similarity is not None else (1.0 - distance), 6
        )
    return response


async def _emit_decision(record: DecisionRecord):
    """Send the routing decision to sentinel as a span."""
    router_metrics.record_decision(record)
    if not sentinel_client:
        return
    now = datetime.utcnow().isoformat() + "Z"
    await sentinel_client.log_span(
        {
            "trace_id": record.request_id,
            "span_id": str(uuid.uuid4()),
            "workspace_id": record.workspace_id,
            "service": "router",
            "operation": "route_decision",
            "start_time": now,
            "end_time": now,
            "status": record.status,
            "attributes": record.as_attributes(),
        }
    )


def _apply_profile(req: ChatRequest, profile: RouteProfile) -> ChatRequest:
    """Overlay profile defaults onto the request without clobbering explicits."""
    updates: Dict[str, Any] = {}
    if profile.model and not getattr(req, "_model_explicit", False):
        updates["model"] = profile.model
    if profile.temperature is not None and req.temperature is None:
        updates["temperature"] = profile.temperature
    if profile.max_tokens is not None and req.max_tokens is None:
        updates["max_tokens"] = profile.max_tokens

    messages = list(req.messages)
    if profile.system_prompt and not any(m.role == "system" for m in messages):
        messages.insert(0, Message(role="system", content=profile.system_prompt))
        updates["messages"] = messages

    if not updates:
        return req
    return req.model_copy(update=updates)


# ── Dispatch ─────────────────────────────────────────────────────

async def _dispatch_chat(
    req: ChatRequest,
    request: Request,
    workspace_id: str,
    *,
    authenticated: bool = False,
) -> Dict[str, Any]:
    if not registry:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    record = DecisionRecord(
        request_id=request_id,
        workspace_id=workspace_id,
        authenticated=authenticated,
        model=req.model,
    )

    if req.stream:
        # Accepting `stream: true` and returning a complete body silently lies
        # to the client. Refuse until SSE passthrough exists.
        raise HTTPException(
            status_code=400,
            detail="Streaming is not supported by this router yet; set stream=false",
        )

    bypass_cache = _cache_bypassed(request, req.enable_cache)

    # Rate limit
    if rate_limiter:
        allowed, retry_after = await rate_limiter.check(workspace_id, req.model)
        if not allowed:
            raise HTTPException(
                status_code=429, detail=f"Rate limit exceeded. Retry after {retry_after}s"
            )

    # ── 1) Exact cache, before any embedding ─────────────────────
    # This path must stay cheap. Embedding first would put 10-40ms in front of
    # the fastest response the router can give.
    exact_key = _exact_cache_key(
        "chat", req.model, req.messages, req.temperature or 0.7, req.tools
    )
    if not bypass_cache and cache:
        cached = await cache.get(exact_key)
        if cached:
            latency_ms = (time.perf_counter() - t0) * 1000
            # An exact hit never embeds, so it cannot classify. The intent
            # stored alongside the entry is what makes this field truthful.
            stored_intent = cached.get("intent", "general")
            out = _enrich(
                dict(cached),
                provider=cached.get("provider", "cache"),
                fallback=False,
                cache_hit=True,
                cache_type="exact",
                latency_ms=latency_ms,
                route_target="cache/exact",
                intent=stored_intent,
                intent_confidence=float(cached.get("intent_confidence") or 0.0),
                profile=cached.get("profile"),
                policy_action=cached.get("policy_action", "allow"),
                egress_class=cached.get("egress_class", "any"),
            )
            record.intent = stored_intent
            record.intent_method = "cached"
            record.cache_hit = True
            record.cache_type = "exact"
            record.billable = False
            record.route_target = "cache/exact"
            record.latency_ms = latency_ms
            await _emit_decision(record)
            return out

    # ── 2) Sensitivity, on the raw text ──────────────────────────
    full_text = extract_user_text(req.messages)
    verdict = PolicyVerdict(text=full_text)
    if policy_engine:
        try:
            verdict = policy_engine.evaluate(full_text, workspace_id)
        except PolicyError as e:
            record.status = "error"
            record.error = f"policy_unavailable: {e}"
            record.latency_ms = (time.perf_counter() - t0) * 1000
            await _emit_decision(record)
            raise HTTPException(
                status_code=503,
                detail="Policy engine unavailable and fail_closed is set",
            )

    record.policy_action = verdict.action.value
    record.policy_rules = verdict.rules
    record.policy_detectors = verdict.detectors
    record.injection_score = verdict.injection_score
    record.redacted = verdict.redacted
    record.egress_class = verdict.egress_class

    if verdict.blocked:
        record.status = "blocked"
        record.billable = False
        record.latency_ms = (time.perf_counter() - t0) * 1000
        await _emit_decision(record)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "blocked_by_policy",
                "reason": verdict.reason,
                "rules": verdict.rules,
            },
        )

    if verdict.redacted and verdict.text is not None:
        req = req.model_copy(
            update={
                "messages": _redact_messages(req.messages, full_text, verdict.text)
            }
        )

    # ── 3) Embed once, then classify and look up the cache ───────
    classification_text = select_classification_text(
        req.messages,
        history_decay=classifier.config.history_decay if classifier else 0.35,
    )
    embedding = None
    want_embedding = bool(
        (semantic_cache and semantic_cache.enabled and not bypass_cache)
        or (classifier and classifier.is_ready)
    )
    if want_embedding and semantic_cache:
        embedding = await semantic_cache.embed(classification_text or req.model)

    intent_result = (
        classifier.classify(classification_text, embedding)
        if classifier
        else IntentResult("general", 0.0, 0.0, "disabled")
    )
    record.intent = intent_result.intent
    record.intent_confidence = intent_result.confidence
    record.intent_margin = intent_result.margin
    record.intent_method = intent_result.method
    record.intent_abstained = intent_result.abstained

    profile = profiles.for_intent(intent_result.intent) if profiles else RouteProfile("default")
    record.profile = profile.name

    # Explicit client model beats the profile default.
    model_explicit = bool(req.model) and req.model != os.environ.get(
        "DEFAULT_CHAT_MODEL", "llama3.1"
    )
    if profile.model and not model_explicit:
        req = req.model_copy(update={"model": profile.model})
    req = _apply_profile(req, profile)
    record.model = req.model

    cacheable = (
        not bypass_cache
        and verdict.cacheable
        and profile.cache.enabled
    )
    sig = cache_signature(req.model, _system_prompt(req.messages), req.temperature or 0.7)
    partition = (
        intent_result.intent
        if (profile.cache.partition and not intent_result.abstained)
        else None
    )

    # ── 4) Semantic cache ────────────────────────────────────────
    if cacheable and semantic_cache and semantic_cache.enabled and embedding:
        hit = await semantic_cache.lookup(
            workspace_id,
            embedding,
            sig=sig,
            partition=partition,
            distance_threshold=profile.cache.distance_threshold,
        )
        if hit:
            payload, distance, meta = hit
            latency_ms = (time.perf_counter() - t0) * 1000
            out = _enrich(
                dict(payload),
                provider=payload.get("provider", "cache"),
                fallback=False,
                cache_hit=True,
                cache_type="semantic",
                latency_ms=latency_ms,
                route_target="cache/semantic",
                intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                profile=profile.name,
                policy_action=verdict.action.value,
                egress_class=verdict.egress_class,
                distance=distance,
            )
            record.cache_hit = True
            record.cache_type = "semantic"
            record.billable = False
            record.route_target = "cache/semantic"
            record.latency_ms = latency_ms
            await _emit_decision(record)
            return out

    # ── 5) Retrieval augmentation ────────────────────────────────
    retrieval_used = False
    if profile.retrieval and mind_client and mind_client.enabled:
        results = await mind_client.query(
            classification_text, workspace_id, top_k=profile.retrieval_top_k
        )
        context = mind_client.format_context(results)
        if context:
            retrieval_used = True
            record.retrieval_used = True
            record.retrieval_hits = len(results)
            req = req.model_copy(
                update={"messages": _prepend_context(req.messages, context)}
            )

    # ── 6) Route ─────────────────────────────────────────────────
    local_only = verdict.local_only
    chain = registry.build_route_chain(
        req.model,
        preferred_provider=req.preferred_target,
        fallback_provider=req.fallback,
        pool=profile.pool or None,
        local_only=local_only,
    )
    record.eligible_pool = [p.name for p in chain]

    if not chain:
        record.status = "error"
        record.billable = False
        record.latency_ms = (time.perf_counter() - t0) * 1000
        if local_only:
            record.error = "no_local_provider"
            await _emit_decision(record)
            # Falling back to a cloud provider here would defeat the verdict,
            # so refusing is the only correct answer.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Policy requires a local provider for this prompt and no "
                    "healthy local provider is available"
                ),
            )
        record.error = "no_provider"
        await _emit_decision(record)
        raise HTTPException(
            status_code=503, detail=f"No healthy provider available for model: {req.model}"
        )

    response: Optional[Dict[str, Any]] = None
    provider = None
    used_fallback = False
    last_error: Optional[Exception] = None

    for attempt, candidate in enumerate(chain):
        try:
            response = await candidate.chat(req)
            provider = candidate
            used_fallback = attempt > 0
            break
        except Exception as e:
            last_error = e

    if response is None or provider is None:
        record.status = "error"
        record.error = str(last_error)
        record.billable = False
        record.latency_ms = (time.perf_counter() - t0) * 1000
        await _emit_decision(record)
        raise HTTPException(status_code=502, detail=f"Provider error: {last_error}")

    usage = response.get("usage", {})
    if usage_tracker:
        await usage_tracker.record(workspace_id, provider.name, req.model, usage)
    if rate_limiter:
        await rate_limiter.record(workspace_id, req.model, usage)

    latency_ms = (time.perf_counter() - t0) * 1000
    route_target = f"{provider.name}/{req.model}"
    out = _enrich(
        response if isinstance(response, dict) else dict(response),
        provider=provider.name,
        fallback=used_fallback,
        cache_hit=False,
        cache_type=None,
        latency_ms=latency_ms,
        route_target=route_target,
        intent=intent_result.intent,
        intent_confidence=intent_result.confidence,
        profile=profile.name,
        policy_action=verdict.action.value,
        egress_class=verdict.egress_class,
        retrieval_used=retrieval_used,
    )

    record.provider = provider.name
    record.route_target = route_target
    record.fallback = used_fallback
    record.latency_ms = latency_ms

    # ── 7) Store caches ──────────────────────────────────────────
    if cacheable and cache:
        await cache.set(exact_key, out, ttl=cache_ttl)

    if cacheable and semantic_cache and semantic_cache.enabled and embedding:
        await semantic_cache.store(
            workspace_id,
            embedding,
            out,
            model=req.model,
            prompt_preview=classification_text or "",
            intent=intent_result.intent,
            sig=sig,
            partition=partition,
        )

    await _emit_decision(record)
    return out


def _redact_messages(
    messages: List[Message], original: str, redacted: str
) -> List[Message]:
    """Apply the policy's redaction to the user turns."""
    from kubemind_policy import redact_string

    out: List[Message] = []
    for m in messages:
        if m.role == "user":
            text, _ = redact_string(m.content)
            out.append(m.model_copy(update={"content": text}))
        else:
            out.append(m)
    return out


def _prepend_context(messages: List[Message], context: str) -> List[Message]:
    out = list(messages)
    insert_at = 0
    for idx, m in enumerate(out):
        if m.role == "system":
            insert_at = idx + 1
    out.insert(insert_at, Message(role="system", content=context))
    return out


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "router",
        "version": "0.3.0",
        "providers_loaded": len(registry.providers) if registry else 0,
        "cache_connected": cache.is_connected if cache else False,
        "semantic_cache": bool(semantic_cache and semantic_cache.enabled),
        "intent_classifier": (
            "semantic" if (classifier and classifier.is_ready) else "rules"
        ),
        "policy_enabled": bool(policy_engine and policy_engine.enabled),
        "auth": "enforced" if (authenticator and not authenticator.open_mode) else "open",
        "retrieval": bool(mind_client and mind_client.enabled),
    }


@app.get("/metrics")
async def prometheus_metrics():
    return PlainTextResponse(
        content=router_metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest, request: Request, auth=Depends(get_auth)
):
    result = await _dispatch_chat(
        req, request, auth.workspace_id, authenticated=auth.authenticated
    )
    return JSONResponse(content=result)


@app.post("/v1/route", response_model=RouteResponse)
async def route_prompt(
    req: RouteRequest, request: Request, auth=Depends(get_auth)
):
    """Landing/SDK-oriented semantic route endpoint."""
    model = req.model or os.environ.get("DEFAULT_CHAT_MODEL", "llama3.1")
    chat_req = ChatRequest(
        model=model,
        messages=[Message(role="user", content=req.prompt)],
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        preferred_target=req.preferred_target,
        fallback=req.fallback,
        enable_cache=req.enable_cache,
    )
    result = await _dispatch_chat(
        chat_req, request, auth.workspace_id, authenticated=auth.authenticated
    )

    content = ""
    choices = result.get("choices") or []
    if choices:
        content = (
            choices[0].get("message", {}).get("content")
            or choices[0].get("text")
            or ""
        )

    return RouteResponse(
        content=content,
        latency_ms=float(result.get("latency_ms") or 0),
        cache_hit=bool(result.get("cache_hit")),
        cache_type=result.get("cache_type"),
        provider=result.get("provider"),
        route_target=result.get("route_target"),
        intent=result.get("intent"),
        intent_confidence=result.get("intent_confidence"),
        profile=result.get("profile"),
        policy_action=result.get("policy_action"),
        egress_class=result.get("egress_class"),
        retrieval_used=bool(result.get("retrieval_used")),
        model=result.get("model") or model,
        usage=result.get("usage"),
        distance=result.get("distance"),
        similarity=result.get("similarity"),
        fallback=bool(result.get("fallback")),
        raw=result,
    )


@app.post("/v1/embeddings")
async def embeddings(
    req: EmbeddingsRequest, request: Request, auth=Depends(get_auth)
):
    if not registry:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    provider = registry.select_provider(req.model, policy="cost")
    if not provider:
        raise HTTPException(status_code=503, detail="No healthy provider available")

    try:
        response = await provider.embeddings(req)
        usage = response.get("usage", {})
        if usage_tracker:
            await usage_tracker.record(
                auth.workspace_id, provider.name, req.model, usage
            )
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/v1/providers/health")
async def providers_health(auth=Depends(get_auth)):
    if not registry:
        return []
    return await registry.health_check_all()


@app.get("/v1/intents")
async def list_intents(auth=Depends(get_auth)):
    """What the classifier knows and which profile each intent resolves to."""
    if not classifier or not profiles:
        return {"intents": [], "ready": False}
    return {
        "ready": classifier.is_ready,
        "mode": "semantic" if classifier.is_ready else "rules",
        "config": {
            "margin_threshold": classifier.config.margin_threshold,
            "min_similarity": classifier.config.min_similarity,
            "knn_k": classifier.config.knn_k,
        },
        "intents": [
            {
                "name": name,
                "examples": len(classifier.index.get(name, [])),
                "profile": profiles.for_intent(name).name,
                "pool": profiles.for_intent(name).pool,
                "model": profiles.for_intent(name).model,
                "retrieval": profiles.for_intent(name).retrieval,
            }
            for name in classifier.intents
        ],
    }


@app.post("/v1/classify")
async def classify_prompt(payload: Dict[str, Any], auth=Depends(get_auth)):
    """Dry-run the classifier and policy without dispatching anywhere.

    The eval harness and anyone tuning thresholds needs to see the decision
    without paying for a completion.
    """
    text = str(payload.get("prompt") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    embedding = None
    if semantic_cache and classifier and classifier.is_ready:
        embedding = await semantic_cache.embed(text)

    result = (
        classifier.classify(text, embedding)
        if classifier
        else IntentResult("general", 0.0, 0.0, "disabled")
    )
    profile = profiles.for_intent(result.intent) if profiles else None

    verdict = PolicyVerdict(text=text)
    if policy_engine:
        try:
            verdict = policy_engine.evaluate(text, auth.workspace_id)
        except PolicyError as e:
            raise HTTPException(status_code=503, detail=str(e))

    return {
        **result.as_attributes(),
        "scores": {k: round(v, 6) for k, v in result.scores.items()},
        "profile": profile.name if profile else None,
        "pool": profile.pool if profile else [],
        **verdict.as_attributes(),
    }


@app.get("/v1/usage")
async def usage(request: Request, auth=Depends(get_auth)):
    workspace_id = auth.workspace_id
    if not usage_tracker:
        return {
            "workspace_id": workspace_id,
            "total_requests": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
        }
    return await usage_tracker.get_summary(workspace_id)


@app.get("/v1/routing/report")
async def routing_report(auth=Depends(get_auth)):
    """Per-intent routing outcomes.

    Cache hits are counted as zero cost. They replay the stored `usage` numbers
    from the original completion, so summing `usage` across responses would
    overcount spend and hide exactly the saving this report exists to show.
    """
    return router_metrics.routing_report()


@app.post("/v1/cache/clear")
async def cache_clear(_admin=Depends(require_admin)):
    if cache:
        await cache.clear()
    return {"status": "ok", "message": "Cache cleared"}


@app.get("/v1/cache/stats")
async def cache_stats(auth=Depends(get_auth)):
    if not cache:
        return {"connected": False}
    stats = await cache.stats()
    stats["semantic_enabled"] = bool(semantic_cache and semantic_cache.enabled)
    stats["semantic_threshold"] = (
        semantic_cache.distance_threshold if semantic_cache else None
    )
    stats["partition_by_intent"] = bool(
        semantic_cache and semantic_cache.partition_by_intent
    )
    return stats
