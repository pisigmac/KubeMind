from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class SpanIngest(BaseModel):
    trace_id: str = Field(..., description="Unique trace identifier")
    span_id: str = Field(..., description="Unique span identifier")
    parent_id: Optional[str] = Field(default=None, description="Parent span ID for nested spans")
    workspace_id: str = Field(default="default", description="Workspace scope")
    service: str = Field(..., description="Service name: router | mind | agents | sentinel")
    operation: str = Field(..., description="Operation type: llm_call | tool_call | ingest | query | plan | route | cache_hit")
    start_time: str = Field(..., description="ISO 8601 timestamp")
    end_time: Optional[str] = Field(default=None, description="ISO 8601 timestamp")
    status: str = Field(default="ok", pattern="^(ok|error|warning)$")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value data")

class SpanQuery(BaseModel):
    workspace_id: str = "default"
    service: Optional[str] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

class SpanResponse(BaseModel):
    id: int
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    workspace_id: str
    service: str
    operation: str
    start_time: str
    end_time: Optional[str]
    status: str
    attributes: Dict[str, Any]
    created_at: str

class MetricsResponse(BaseModel):
    workspace_id: str
    total_spans: int
    total_errors: int
    error_rate: float
    avg_duration_ms: float
    services: Dict[str, Dict[str, Any]]
    operations: Dict[str, Dict[str, Any]]
    time_range: Dict[str, str]

class ExportResponse(BaseModel):
    workspace_id: str
    spans: List[SpanResponse]
    count: int
    exported_at: str
