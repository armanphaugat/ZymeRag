from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class DecisionEnum(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class ToolAction(BaseModel):
    """Incoming agent tool action payload."""
    action_id: UUID = Field(default_factory=uuid4, description="Unique action UUID")
    agent_id: str = Field(..., description="Calling AI agent identifier")
    user_id: str = Field(..., description="End-user on whose behalf the action is run")
    tool: str = Field(..., description="Target tool name (e.g., 'payment', 'crm', 'email')")
    operation: str = Field(..., description="Target operation (e.g., 'transfer_funds', 'delete_customer')")
    resource: str = Field(..., description="Target resource URI or entity identifier")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Action arguments/parameters")
    context: Dict[str, Any] = Field(default_factory=dict, description="Session/environmental context")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of invocation")


class DecisionResponse(BaseModel):
    """Evaluation decision returned to the calling agent or orchestrator."""
    action_id: UUID
    decision: DecisionEnum
    flow_id: str
    matched_rule_id: Optional[str] = None
    reason: str
    source_clause: Optional[str] = None
    required_approval_role: Optional[str] = None
    approval_id: Optional[str] = None


class ExecutionResult(BaseModel):
    """Result of action execution."""
    action_id: UUID
    status: str
    decision: DecisionEnum
    executed: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    approval_id: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    """Payload for human reviewer decision on an escalated action."""
    decision: str = Field(..., description="'APPROVED' or 'REJECTED'")
    decided_by: Optional[str] = Field(None, description="Identifier of the human reviewer")
    reason: Optional[str] = Field(None, description="Optional justification for decision")


class FlowRegistrationRequest(BaseModel):
    """Register or update a tool + operation mapping in the flow_registry."""
    tool: str
    operation: str
    flow_id: str
    description: Optional[str] = None
