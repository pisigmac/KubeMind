from pydantic import BaseModel
from typing import Dict, Optional, Any
from datetime import datetime

class SpanIngest(BaseModel):
    trace_id: str
    span_id: str
    parent_id: Optional[str] = None
    workspace_id: str = "default"
    service: str  # router | agents | mind
    operation: str  # llm_call | tool_call | ingest | query | plan
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "ok"  # ok | error
    attributes: Dict[str, Any] = {}
