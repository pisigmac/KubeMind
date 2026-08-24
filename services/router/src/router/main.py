import os
import time
import uuid
import hashlib
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List, Tuple
from dataclasses import asdict

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from kubemind_policy.streaming import StreamingDeAnonymizer
from kubemind_policy.redaction import restore_string

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
from router.mind_client import (
    STATUS_UNAVAILABLE,
    MindClient,
    RetrievalOutcome,
)
from router.intent import (
    IntentClassifier,
    IntentResult,
    extract_user_text,
    select_classification_text,
)
from router.policy import PolicyEngine, PolicyError, PolicyVerdict
from router.profiles import ProfileRegistry, RouteProfile
from router.auth import (
    API_KEY_HEADER,
    WORKSPACE_HEADER,
    AuthError,
    Authenticator,
    cors_origins,
    deployment_profile,
    is_production,
)
from router import metrics as router_metrics
from router.feedback import FeedbackConfig, FeedbackLog
from router.cascade import (
    CascadeConfig,
    extract_answer_text,
    reorder_for_cascade,
    should_escalate,
)

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
feedback_log: Optional[FeedbackLog] = None
cascade_config: CascadeConfig = CascadeConfig()
cache_ttl: int = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    global registry, cache, semantic_cache, rate_limiter, usage_tracker
    global sentinel_client, mind_client, classifier, policy_engine, profiles
    global authenticator, feedback_log, cascade_config, cache_ttl

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
    authenticator.assert_production_safe("router")
    print(authenticator.startup_banner())

    feedback_log = FeedbackLog(
        redis_client=cache.client,
        config=FeedbackConfig.from_config(registry.config),
    )
    cascade_config = CascadeConfig.from_dict(
        (registry.config.get("routing") or {}).get("cascade")
    )

    mind_client = MindClient()
    await mind_client.init()

    classifier = IntentClassifier.from_config(registry.config)
    indexed = await classifier.build_index(semantic_cache.embed)
    print(
        f"[router] intent classifier: {len(classifier.intents)} intents, "
        f"{indexed} examples indexed, "
        f"{'semantic' if classifier.is_ready else 'rules-only'} mode"
        + (", linear_head=on" if classifier.linear_head else "")
    )
    print(
        f"[router] semantic cache backend={semantic_cache.backend}; "
        f"cascade={'on' if cascade_config.enabled else 'off'}"
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
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
    prefix: str,
    workspace_id: str,
    req: ChatRequest,
    profile: RouteProfile,
    policy_signature: Dict[str, Any],
) -> str:
    data = {
        "schema": "2",
        "workspace_id": workspace_id,
        "model": req.model,
        "messages": [(m.role, m.content, m.name) for m in req.messages],
        "temperature": req.temperature,
        "top_p": req.top_p,
        "max_tokens": req.max_tokens,
        "tools": req.tools,
        "tool_choice": req.tool_choice,
        "preferred_target": req.preferred_target,
        "fallback": req.fallback,
        "routing_policy": req.policy,
        "max_latency_ms": req.max_latency_ms,
        "profile": asdict(profile),
        "policy": policy_signature,
    }
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
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
    retrieval_status: Optional[str] = None,
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
    if retrieval_status:
        response["retrieval_status"] = retrieval_status
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

    bypass_cache = _cache_bypassed(request, req.enable_cache)

    # Rate limit
    if rate_limiter:
        allowed, retry_after = await rate_limiter.check(workspace_id, req.model)
        if not allowed:
            raise HTTPException(
                status_code=429, detail=f"Rate limit exceeded. Retry after {retry_after}s"
            )

    # Policy must execute before every cache read. Serving cached content is
    # still an egress decision and cannot bypass changed Workspace policy.
    full_text = extract_user_text(req.messages)
    verdict = PolicyVerdict(text=full_text)
    if policy_engine:
        try:
            verdict = policy_engine.evaluate(full_text, workspace_id)
        except PolicyError:
            record.status = "error"
            record.error = "policy_unavailable"
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

    active_token_map: Dict[str, str] = {}
    if verdict.redacted and verdict.text is not None:
        redacted_messages, active_token_map = _redact_messages(
            req.messages, full_text, verdict
        )
        req = req.model_copy(update={"messages": redacted_messages})

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

    try:
        intent_result = (
            classifier.classify(classification_text, embedding)
            if classifier
            else IntentResult("general", 0.0, 0.0, "disabled", abstained=True)
        )
    except Exception:
        intent_result = IntentResult(
            "general", 0.0, 0.0, "classifier_failure", abstained=True
        )
    record.intent = intent_result.intent
    record.intent_confidence = intent_result.confidence
    record.intent_margin = intent_result.margin
    record.intent_method = intent_result.method
    record.intent_abstained = intent_result.abstained

    profile = profiles.for_intent(intent_result.intent) if profiles else RouteProfile("default")
    record.profile = profile.name
    record.considered_pool = list(profile.pool)

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
        and not req.tools
        and not profile.retrieval
    )
    rules = policy_engine.rules_for(workspace_id) if policy_engine else []
    policy_signature = {
        "action": verdict.action.value,
        "egress_class": verdict.egress_class,
        "rules": [(rule.name, rule.threshold) for rule in rules],
    }
    exact_key = _exact_cache_key(
        "chat", workspace_id, req, profile, policy_signature
    )

    if cacheable and cache:
        cached = await cache.get(exact_key)
        if cached:
            latency_ms = (time.perf_counter() - t0) * 1000
            record.route_reason_code = "CACHE_EXACT_HIT"
            out = _enrich(
                dict(cached),
                provider=cached.get("provider", "cache"),
                fallback=False,
                cache_hit=True,
                cache_type="exact",
                latency_ms=latency_ms,
                route_target="cache/exact",
                intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                profile=profile.name,
                policy_action=verdict.action.value,
                egress_class=verdict.egress_class,
            )
            out["routing_decision"] = {
                "reason_code": record.route_reason_code,
                "intent": record.intent,
                "profile": record.profile,
                "considered_providers": ["cache/exact"],
                "eligible_providers": ["cache/exact"],
                "selected_provider": "cache/exact",
                "retrieval_status": None,
                "retrieval_hits": 0,
            }
            record.cache_hit = True
            record.cache_type = "exact"
            record.billable = False
            record.route_target = "cache/exact"
            record.latency_ms = latency_ms
            await _emit_decision(record)
            return _restore_response(out, active_token_map)
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
            record.route_reason_code = "CACHE_SEMANTIC_HIT"
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
            out["routing_decision"] = {
                "reason_code": record.route_reason_code,
                "intent": record.intent,
                "profile": record.profile,
                "considered_providers": ["cache/semantic"],
                "eligible_providers": ["cache/semantic"],
                "selected_provider": "cache/semantic",
                "retrieval_status": None,
                "retrieval_hits": 0,
                "distance": distance,
            }
            record.cache_hit = True
            record.cache_type = "semantic"
            record.billable = False
            record.route_target = "cache/semantic"
            record.latency_ms = latency_ms
            await _emit_decision(record)
            return _restore_response(out, active_token_map)

    # ── 5) Retrieval augmentation ────────────────────────────────
    retrieval_used = False
    retrieval_status = None
    if profile.retrieval:
        outcome = RetrievalOutcome(STATUS_UNAVAILABLE)
        if mind_client:
            outcome = await mind_client.retrieve(
                classification_text, workspace_id, top_k=profile.retrieval_top_k
            )
        retrieval_status = outcome.status
        record.retrieval_status = outcome.status
        record.retrieval_hits = len(outcome.hits)
        if outcome.status == STATUS_UNAVAILABLE and is_production():
            record.status = "error"
            record.error = "retrieval_unavailable"
            record.billable = False
            record.latency_ms = (time.perf_counter() - t0) * 1000
            await _emit_decision(record)
            raise HTTPException(
                status_code=503,
                detail="Knowledge retrieval unavailable",
            )
        if outcome.used:
            retrieval_used = True
            record.retrieval_used = True
            req = req.model_copy(
                update={"messages": _prepend_context(req.messages, outcome.context)}
            )

    # ── 6) Route ─────────────────────────────────────────────────
    local_only = verdict.local_only
    chain = registry.build_route_chain(
        req.model,
        preferred_provider=req.preferred_target,
        fallback_provider=req.fallback,
        pool=profile.pool or None,
        local_only=local_only,
        policy=req.policy or "cost",
        max_latency_ms=req.max_latency_ms,
    )
    chain = reorder_for_cascade(
        chain, config=cascade_config, is_local=registry.is_local
    )
    record.eligible_pool = [p.name for p in chain]
    if local_only:
        record.route_reason_code = "POLICY_LOCAL_ONLY"
    elif intent_result.method == "classifier_failure":
        record.route_reason_code = "CLASSIFIER_FAILURE_FALLBACK"
    elif intent_result.abstained:
        record.route_reason_code = "CLASSIFIER_LOW_CONFIDENCE_FALLBACK"
    elif req.preferred_target and chain and chain[0].name == (
        registry.resolve_target_alias(req.preferred_target) or req.preferred_target
    ):
        record.route_reason_code = "PREFERRED_PROVIDER_ALLOWED"
    elif req.preferred_target:
        record.route_reason_code = "PREFERRED_PROVIDER_UNAVAILABLE"
    else:
        record.route_reason_code = "POLICY_ORDERED_SELECTION"

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

    if req.stream:
        selected_candidate = chain[0] if chain else None
        if not selected_candidate:
            record.status = "error"
            record.error = "no_eligible_provider"
            await _emit_decision(record)
            raise HTTPException(status_code=503, detail="No eligible provider available for streaming")

        async def sse_event_stream():
            de_anon = StreamingDeAnonymizer(active_token_map)
            if hasattr(selected_candidate, "chat_stream"):
                async for raw_chunk in selected_candidate.chat_stream(req):
                    if raw_chunk.startswith("data: ") and not raw_chunk.startswith("data: [DONE]"):
                        payload_str = raw_chunk[6:].strip()
                        try:
                            data = json.loads(payload_str)
                            choices = data.get("choices", [])
                            if choices and "delta" in choices[0]:
                                delta_content = choices[0]["delta"].get("content", "")
                                if delta_content:
                                    transformed = de_anon.transform_chunk(delta_content)
                                    choices[0]["delta"]["content"] = transformed
                                    data["choices"] = choices
                                    yield f"data: {json.dumps(data)}\n\n"
                                else:
                                    yield raw_chunk
                            else:
                                yield raw_chunk
                        except Exception:
                            yield raw_chunk
                    elif raw_chunk.startswith("data: [DONE]"):
                        flushed = de_anon.flush()
                        if flushed:
                            flush_chunk = {
                                "id": f"chatcmpl-{int(time.time()*1000)}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": req.model,
                                "choices": [{"index": 0, "delta": {"content": flushed}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(flush_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                    else:
                        yield raw_chunk
            else:
                resp = await selected_candidate.chat(req)
                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                restored = restore_string(content, active_token_map)
                chunk = {
                    "id": resp.get("id", f"chatcmpl-{int(time.time()*1000)}"),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": restored}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

        record.status = "success"
        record.provider = selected_candidate.name
        record.latency_ms = (time.perf_counter() - t0) * 1000
        await _emit_decision(record)
        return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

    response: Optional[Dict[str, Any]] = None
    provider = None
    used_fallback = False
    # Kept if cascade tries a stronger model and that attempt fails -- a thin
    # cheap answer beats no answer.
    primary_response: Optional[Dict[str, Any]] = None
    primary_provider = None

    for attempt, candidate in enumerate(chain):
        call_start = time.perf_counter()
        try:
            candidate_response = await candidate.chat(req)
            # Feeds the `latency` policy and the max_latency_ms budget, which
            # would otherwise have nothing measured to work from.
            candidate.observe_latency((time.perf_counter() - call_start) * 1000)
            response = candidate_response
            provider = candidate
            used_fallback = attempt > 0

            # Optional cascade: keep the cheap answer only when it looks good.
            if attempt == 0 and len(chain) > 1:
                primary_response = candidate_response
                primary_provider = candidate
                decision = should_escalate(
                    config=cascade_config,
                    confidence=intent_result.confidence,
                    abstained=intent_result.abstained,
                    answer_text=extract_answer_text(candidate_response),
                    local_only=local_only,
                )
                if decision.should_escalate:
                    record.cascade_escalated = True
                    record.cascade_reason = decision.reason
                    continue
            break
        except Exception:
            if attempt > 0 and primary_response is not None:
                # Escalation failed; serve the first answer.
                response = primary_response
                provider = primary_provider
                used_fallback = False
                break

    if response is None or provider is None:
        record.status = "error"
        record.error = "provider_unavailable"
        record.billable = False
        record.latency_ms = (time.perf_counter() - t0) * 1000
        await _emit_decision(record)
        raise HTTPException(status_code=502, detail="Provider unavailable")

    if record.cascade_escalated and used_fallback:
        used_fallback = True

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
        retrieval_status=retrieval_status,
    )
    out["routing_decision"] = {
        "reason_code": record.route_reason_code,
        "intent": record.intent,
        "profile": record.profile,
        "considered_providers": record.considered_pool,
        "eligible_providers": record.eligible_pool,
        "selected_provider": provider.name,
        "retrieval_status": retrieval_status,
        "retrieval_hits": record.retrieval_hits,
    }

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
    await _capture_feedback(
        record,
        classification_text,
        intent_result,
        provider.name,
        used_fallback,
    )
    return _restore_response(out, active_token_map)


async def _capture_feedback(
    record: DecisionRecord,
    prompt: str,
    intent_result,
    provider_name: Optional[str],
    used_fallback: bool,
):
    """Queue the cases a labelled set is short of.

    Abstentions, near-threshold predictions and provider fallbacks are the
    examples worth a human's time. Collecting them costs nothing here and is
    what keeps the classifier honest as traffic drifts.
    """
    if not feedback_log:
        return
    feedback_log.observe(record.intent)
    reason = feedback_log.should_capture(
        abstained=record.intent_abstained,
        confidence=record.intent_confidence,
        used_fallback=used_fallback,
        policy_action=record.policy_action,
    )
    if not reason:
        return
    try:
        await feedback_log.capture(
            workspace_id=record.workspace_id,
            reason=reason,
            prompt=prompt or "",
            predicted_intent=record.intent,
            confidence=record.intent_confidence,
            margin=getattr(intent_result, "margin", 0.0),
            scores=getattr(intent_result, "scores", {}) or {},
            profile=record.profile or "",
            provider=provider_name,
            sensitive=bool(record.policy_detectors),
        )
    except Exception:
        # Label collection is never worth failing a served request over.
        pass


def _redact_messages(
    messages: List[Message], full_text: str, verdict
) -> Tuple[List[Message], Dict[str, str]]:
    """Apply the policy's pseudonymization to user turns and capture the token mapping."""
    from kubemind_policy import pseudonymize_string

    out: List[Message] = []
    token_map: Dict[str, str] = dict(getattr(verdict, "token_map", {}) or {})
    for m in messages:
        if m.role == "user":
            text, m_map, _ = pseudonymize_string(m.content)
            token_map.update(m_map)
            out.append(m.model_copy(update={"content": text}))
        else:
            out.append(m)
    return out, token_map


def _restore_response(response: Any, token_map: Dict[str, str]) -> Any:
    """Restore pseudonymized tokens in the LLM's generated response before returning to user.
    
    Walks message.content, text, tool_calls[].function.arguments, and function_call.arguments.
    """
    if not token_map or not response:
        return response
    from kubemind_policy import restore_string

    if isinstance(response, dict):
        resp_dict = dict(response)
        if "choices" in resp_dict and isinstance(resp_dict["choices"], list):
            new_choices = []
            for choice in resp_dict["choices"]:
                c = dict(choice)
                if "message" in c and isinstance(c["message"], dict):
                    msg = dict(c["message"])
                    if "content" in msg and isinstance(msg["content"], str):
                        msg["content"] = restore_string(msg["content"], token_map)
                    # Restore tokens in tool_calls[].function.arguments
                    if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                        restored_calls = []
                        for tc in msg["tool_calls"]:
                            tc = dict(tc)
                            if "function" in tc and isinstance(tc["function"], dict):
                                fn = dict(tc["function"])
                                if "arguments" in fn and isinstance(fn["arguments"], str):
                                    fn["arguments"] = restore_string(fn["arguments"], token_map)
                                tc["function"] = fn
                            restored_calls.append(tc)
                        msg["tool_calls"] = restored_calls
                    # Restore tokens in legacy function_call.arguments
                    if "function_call" in msg and isinstance(msg["function_call"], dict):
                        fc = dict(msg["function_call"])
                        if "arguments" in fc and isinstance(fc["arguments"], str):
                            fc["arguments"] = restore_string(fc["arguments"], token_map)
                        msg["function_call"] = fc
                    c["message"] = msg
                if "text" in c and isinstance(c["text"], str):
                    c["text"] = restore_string(c["text"], token_map)
                new_choices.append(c)
            resp_dict["choices"] = new_choices
        return resp_dict
    return response


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
        "credential_mode": registry.credential_mode if registry else "uninitialized",
        "credential_warning": (
            "direct mode stores deployment provider credentials in KubeMind"
            if registry and not registry.uses_keymint
            else None
        ),
        "cache_connected": cache.is_connected if cache else False,
        "semantic_cache": bool(semantic_cache and semantic_cache.enabled),
        "intent_classifier": (
            "semantic" if (classifier and classifier.is_ready) else "rules"
        ),
        "policy_enabled": bool(policy_engine and policy_engine.enabled),
        "auth": "enforced" if (authenticator and not authenticator.open_mode) else "open",
        "deployment": deployment_profile(),
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
    auth.assert_scope("chat")
    result = await _dispatch_chat(
        req, request, auth.workspace_id, authenticated=auth.authenticated
    )
    if isinstance(result, StreamingResponse):
        return result

    headers = {
        "X-KubeMind-Trace-ID": str(result.get("id") or uuid.uuid4()),
        "X-KubeMind-Intent": str(result.get("intent") or "default"),
        "X-KubeMind-Provider": str(result.get("provider") or "unknown"),
        "X-KubeMind-Policy-Action": str(result.get("policy_action") or "allow"),
        "X-KubeMind-Cache-Hit": str(bool(result.get("cache_hit"))).lower(),
        "X-KubeMind-Fallback-Used": str(bool(result.get("fallback"))).lower(),
        "X-KubeMind-Latency-MS": str(round(float(result.get("latency_ms") or 0), 2)),
    }
    if result.get("retrieval_status"):
        headers["X-KubeMind-Retrieval-Status"] = str(result.get("retrieval_status"))

    return JSONResponse(content=result, headers=headers)


@app.post("/v1/route", response_model=RouteResponse)
async def route_prompt(
    req: RouteRequest, request: Request, auth=Depends(get_auth)
):
    """Landing/SDK-oriented semantic route endpoint."""
    auth.assert_scope("route")
    model = req.model or os.environ.get("DEFAULT_CHAT_MODEL", "llama3.1")
    chat_req = ChatRequest(
        model=model,
        messages=[Message(role="user", content=req.prompt)],
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        preferred_target=req.preferred_target,
        fallback=req.fallback,
        enable_cache=req.enable_cache,
        policy=req.policy,
        max_latency_ms=req.max_latency_ms,
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
        retrieval_status=result.get("retrieval_status"),
        routing_decision=result.get("routing_decision"),
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
    except Exception:
        raise HTTPException(status_code=502, detail="Provider unavailable")


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


@app.get("/v1/intents/review")
async def list_review_queue(
    limit: int = 50,
    reason: Optional[str] = None,
    include_reviewed: bool = False,
    auth=Depends(get_auth),
):
    """Cases worth a human's attention.

    Abstentions, near-threshold predictions and provider fallbacks. Reviewing
    a random sample of traffic mostly re-confirms what the classifier already
    gets right; these are the examples that carry information.
    """
    if not feedback_log:
        raise HTTPException(status_code=503, detail="Feedback log not initialized")
    return {
        "workspace_id": auth.workspace_id,
        "cases": await feedback_log.pending(
            auth.workspace_id,
            limit=limit,
            reason=reason,
            include_reviewed=include_reviewed,
        ),
    }


@app.post("/v1/intents/review")
async def submit_review(payload: Dict[str, Any], auth=Depends(get_auth)):
    """Attach a human label to a queued case."""
    if not feedback_log:
        raise HTTPException(status_code=503, detail="Feedback log not initialized")
    case_id = payload.get("case_id")
    true_intent = payload.get("intent")
    if not case_id or not true_intent:
        raise HTTPException(status_code=400, detail="case_id and intent are required")

    updated = await feedback_log.review(auth.workspace_id, case_id, true_intent)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")
    return updated


@app.get("/v1/intents/review/summary")
async def review_summary(auth=Depends(get_auth)):
    """Drift signal.

    A rising disagreement rate means the intent definitions no longer describe
    what people are actually asking for, which is a product signal before it
    is a modelling one.
    """
    if not feedback_log:
        raise HTTPException(status_code=503, detail="Feedback log not initialized")
    return await feedback_log.summary(auth.workspace_id)


@app.get("/v1/intents/review/export")
async def export_reviewed(auth=Depends(get_auth)):
    """Human-confirmed labels in eval/dataset.jsonl format.

    Append to the eval set and re-run `make eval`. Only reviewed cases are
    exported: exporting predictions would let the classifier grade its own
    homework.
    """
    if not feedback_log:
        raise HTTPException(status_code=503, detail="Feedback log not initialized")
    body = await feedback_log.export_jsonl(auth.workspace_id)
    return PlainTextResponse(content=body, media_type="application/x-ndjson")


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
        except PolicyError:
            raise HTTPException(status_code=503, detail="Policy engine unavailable")

    return {
        **result.as_attributes(),
        "scores": {k: round(v, 6) for k, v in result.scores.items()},
        "profile": profile.name if profile else None,
        "pool": profile.pool if profile else [],
        **verdict.as_attributes(),
    }


@app.get("/v1/usage")
async def usage(request: Request, auth=Depends(get_auth)):
    auth.assert_scope("usage:read")
    workspace_id = auth.workspace_id
    if not usage_tracker:
        return {
            "workspace_id": workspace_id,
            "total_requests": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
        }
    return await usage_tracker.get_summary(workspace_id)


@app.get("/v1/usage/analytics")
@app.get("/v1/analytics/costs")
async def usage_analytics(
    window_hours: int = 24, auth=Depends(get_auth)
):
    """Aggregate CFO-level financial and usage analytics for a workspace."""
    auth.assert_scope("usage:read")
    workspace_id = auth.workspace_id
    if not usage_tracker:
        return {
            "workspace_id": workspace_id,
            "window_hours": window_hours,
            "total_requests": 0,
            "total_tokens": 0,
            "estimated_spend_usd": 0.0,
            "providers": {},
            "models": {},
        }
    return await usage_tracker.get_analytics(workspace_id, window_hours=window_hours)


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
