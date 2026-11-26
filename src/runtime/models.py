from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class StepSpec(BaseModel):
    step_id: str
    action_name: str
    prompt_template: str
    is_sensitive: bool = False
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    required_inputs: List[str] = Field(default_factory=list)


class WorkflowSpec(BaseModel):
    workflow_id: str
    name: str
    steps: List[StepSpec]


class EscalationTicket(BaseModel):
    ticket_id: str
    workflow_id: str
    step_id: str
    reason: str
    context: Dict[str, Any]


class ExecutionResult(BaseModel):
    workflow_id: str
    status: StepStatus
    outputs: Dict[str, Any] = Field(default_factory=dict)
    escalation: Optional[EscalationTicket] = None
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)
