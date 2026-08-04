from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime

class Message(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: str
    name: Optional[str] = None

class MissionRequest(BaseModel):
    prompt: str = Field(..., description="The mission prompt")
    mode: Literal["sync", "async"] = "sync"
    model: Optional[str] = Field(default=None, description="Override default model")
    tools: Optional[List[str]] = Field(default=None, description="Specific tools to enable")
    max_steps: Optional[int] = Field(default=20, ge=1, le=100)

class MissionResponse(BaseModel):
    id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    tool_calls: int = 0
    tokens_used: int = 0
    duration_ms: int = 0

class MissionStatus(BaseModel):
    id: str
    status: str
    prompt: str
    output: Optional[str] = None
    error: Optional[str] = None
    plan: Optional[List[Dict]] = None
    tool_calls: List[Dict] = []
    tokens_used: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0

class MissionListItem(BaseModel):
    id: str
    status: str
    prompt: str
    created_at: Optional[datetime] = None

class ToolInvokeRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]

class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    enabled: bool = True
