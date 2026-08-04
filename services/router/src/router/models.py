from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union


class Message(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict]] = None
    # Optional routing hints (also used internally by /v1/route)
    preferred_target: Optional[str] = None
    fallback: Optional[str] = None
    enable_cache: Optional[bool] = True


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    provider: Optional[str] = None
    cached: Optional[bool] = False
    cache_hit: Optional[bool] = False
    cache_type: Optional[str] = None
    fallback: Optional[bool] = False
    latency_ms: Optional[float] = None
    route_target: Optional[str] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    profile: Optional[str] = None
    policy_action: Optional[str] = None
    egress_class: Optional[str] = None
    retrieval_used: Optional[bool] = False
    distance: Optional[float] = None
    similarity: Optional[float] = None


class EmbeddingsRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None


class EmbeddingsResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, int]


class UsageReport(BaseModel):
    workspace_id: str
    total_requests: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    providers: Dict[str, Dict[str, Any]] = {}


class RouteRequest(BaseModel):
    """Landing / SDK oriented routing API."""

    prompt: str = Field(..., min_length=1)
    preferred_target: Optional[str] = None
    fallback: Optional[str] = None
    enable_cache: bool = True
    max_latency_ms: Optional[int] = Field(default=None, ge=1)
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)


class RouteResponse(BaseModel):
    content: str
    latency_ms: float
    cache_hit: bool
    cache_type: Optional[str] = None
    provider: Optional[str] = None
    route_target: Optional[str] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    profile: Optional[str] = None
    policy_action: Optional[str] = None
    egress_class: Optional[str] = None
    retrieval_used: bool = False
    model: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    distance: Optional[float] = None
    similarity: Optional[float] = None
    fallback: bool = False
    raw: Optional[Dict[str, Any]] = None


class DecisionRecord(BaseModel):
    """What the router decided, and why.

    One object serving both stories: the routing report reads the intent and
    target fields, the audit trail reads the policy fields.
    """

    request_id: str
    workspace_id: str
    authenticated: bool = False

    intent: str = "general"
    intent_confidence: float = 0.0
    intent_margin: float = 0.0
    intent_method: str = "disabled"
    intent_abstained: bool = False

    policy_action: str = "allow"
    policy_rules: List[str] = []
    policy_detectors: List[str] = []
    injection_score: float = 0.0
    redacted: bool = False
    egress_class: str = "any"

    profile: Optional[str] = None
    eligible_pool: List[str] = []
    route_target: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback: bool = False

    retrieval_used: bool = False
    retrieval_hits: int = 0

    cache_hit: bool = False
    cache_type: Optional[str] = None
    billable: bool = True

    latency_ms: float = 0.0
    status: str = "ok"
    error: Optional[str] = None

    def as_attributes(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)
