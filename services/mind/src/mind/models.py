from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
from enum import Enum

class NodeType(str, Enum):
    DOCUMENT = "document"
    CODE = "code"
    CONVERSATION = "conversation"
    AGENT_MEMORY = "agent_memory"
    PLAN = "plan"

class IngestRequest(BaseModel):
    source: str = Field(..., description="URL, file path, or directory path")
    type: NodeType = Field(default=NodeType.DOCUMENT, description="Node type")
    content: Optional[str] = Field(default=None, description="Direct text content for file uploads")

class IngestResponse(BaseModel):
    ingested: int
    node_ids: List[str]
    workspace_id: str

class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, str]] = Field(default=None, description="Type filters, e.g. {'type': 'code'}")
    top_k: Optional[int] = Field(default=10, ge=1, le=100)

class QueryResult(BaseModel):
    id: str
    type: str
    content: str
    metadata: Dict[str, Any]
    score: float
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    graph_score: Optional[float] = None

class QueryResponse(BaseModel):
    query: str
    results: List[QueryResult]
    count: int
    workspace_id: str

class NodeResponse(BaseModel):
    id: str
    type: str
    workspace_id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    links: List[Dict[str, Any]] = []

class LinkRequest(BaseModel):
    source_id: str
    target_id: str
    link_type: str = "related"

class TypedNode(BaseModel):
    id: str
    workspace_id: str
    type: NodeType
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
