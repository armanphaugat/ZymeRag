import json
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Query, Request
from Backend.Gateway.schemas import (
    ToolAction,
    DecisionEnum,
    DecisionResponse,
    ExecutionResult,
    ApprovalDecisionRequest,
    FlowRegistrationRequest,
)
from Backend.Gateway.classifier import classify_flow, register_flow, list_flows
from Backend.Gateway.policy_engine import evaluate_action_policy
from Backend.Gateway.approvals import (
    create_pending_approval,
    list_pending_approvals,
    get_approval_by_id,
    update_approval_status,
)
from Backend.Gateway.audit import (
    log_audit_event,
    get_audit_trail,
    verify_audit_chain_integrity,
)
from Backend.Gateway.execution import execute_action
from Dbhelper.idempotency_helper import (
    get_idempotent_result,
    save_idempotent_result,
)


async def evaluate_action_handler(action: ToolAction):
    """
    Evaluates an action in real-time against active policies without executing it.
    Zero runtime LLM. Returns ALLOW, BLOCK, or ESCALATE.
    """
    flow_id = await classify_flow(action.tool, action.operation)
    decision = await evaluate_action_policy(action, flow_id)

    approval_id = None
    if decision.decision == DecisionEnum.ESCALATE:
        approval_id = await create_pending_approval(
            action=action,
            rule_id=decision.matched_rule_id,
            required_role=decision.required_approval_role or "admin",
        )
        decision.approval_id = approval_id

    # Log evaluation to cryptographic hash-chained audit log
    await log_audit_event(
        action_id=str(action.action_id),
        tool=action.tool,
        operation=action.operation,
        flow_id=flow_id,
        decision=decision.decision.value,
        agent_id=action.agent_id,
        user_id=action.user_id,
        matched_rule_id=decision.matched_rule_id,
        details={
            "reason": decision.reason,
            "source_clause": decision.source_clause,
            "approval_id": approval_id,
        },
    )

    return decision


async def execute_action_handler(
    action: ToolAction,
    idempotent_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Evaluates and conditionally executes an action:
    - Deduplicates using Postgres-backed idempotency.
    - BLOCK: Prevents execution and logs to audit.
    - ESCALATE: Queues action in approvals for human review.
    - ALLOW: Safely dispatches action to target enterprise service.
    """
    # 1. Idempotency Check
    if isinstance(idempotent_key, str) and idempotent_key.strip():
        cached_res = await get_idempotent_result(idempotent_key)
        if cached_res:
            try:
                return json.loads(cached_res)
            except Exception:
                return {"message": "Duplicate request", "result_id": cached_res}

    flow_id = await classify_flow(action.tool, action.operation)
    eval_res = await evaluate_action_policy(action, flow_id)

    # 2. Case: BLOCK
    if eval_res.decision == DecisionEnum.BLOCK:
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id=flow_id,
            decision="BLOCK",
            agent_id=action.agent_id,
            user_id=action.user_id,
            matched_rule_id=eval_res.matched_rule_id,
            details={"reason": eval_res.reason, "source_clause": eval_res.source_clause},
        )
        res = ExecutionResult(
            action_id=action.action_id,
            status="blocked",
            decision=DecisionEnum.BLOCK,
            executed=False,
            error=eval_res.reason,
        )
        if isinstance(idempotent_key, str) and idempotent_key.strip():
            await save_idempotent_result(idempotent_key, json.dumps(res.model_dump(), default=str))
        return res

    # 3. Case: ESCALATE
    if eval_res.decision == DecisionEnum.ESCALATE:
        approval_id = await create_pending_approval(
            action=action,
            rule_id=eval_res.matched_rule_id,
            required_role=eval_res.required_approval_role or "admin",
        )
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id=flow_id,
            decision="ESCALATE",
            agent_id=action.agent_id,
            user_id=action.user_id,
            matched_rule_id=eval_res.matched_rule_id,
            details={
                "reason": eval_res.reason,
                "source_clause": eval_res.source_clause,
                "approval_id": approval_id,
            },
        )
        res = ExecutionResult(
            action_id=action.action_id,
            status="pending_approval",
            decision=DecisionEnum.ESCALATE,
            executed=False,
            approval_id=approval_id,
            result={
                "message": eval_res.reason,
                "required_role": eval_res.required_approval_role,
            },
        )
        if isinstance(idempotent_key, str) and idempotent_key.strip():
            await save_idempotent_result(idempotent_key, json.dumps(res.model_dump(), default=str))
        return res

    # 4. Case: ALLOW -> Execute action
    await log_audit_event(
        action_id=str(action.action_id),
        tool=action.tool,
        operation=action.operation,
        flow_id=flow_id,
        decision="ALLOW",
        agent_id=action.agent_id,
        user_id=action.user_id,
        matched_rule_id=eval_res.matched_rule_id,
        details={"reason": eval_res.reason, "source_clause": eval_res.source_clause},
    )

    exec_res = await execute_action(action, flow_id)
    if isinstance(idempotent_key, str) and idempotent_key.strip():
        await save_idempotent_result(idempotent_key, json.dumps(exec_res.model_dump(), default=str))
    return exec_res


async def list_approvals_handler(role: Optional[str] = Query(None, description="Filter by required role")):
    """Lists pending approvals awaiting human decision."""
    approvals = await list_pending_approvals(role)
    return {"total": len(approvals), "approvals": approvals}


async def decide_approval_handler(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    request: Request = None,
):
    """
    Decides on an escalated action (APPROVED or REJECTED).
    CRITICAL: Re-validates the action against current rule state before executing.
    """
    approval = await get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval record {approval_id} not found")

    if approval.get("status") != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Approval is already in '{approval.get('status')}' state and cannot be modified."
        )

    decided_by = payload.decided_by
    if not decided_by and request and hasattr(request.state, "user"):
        decided_by = request.state.user
    decided_by = decided_by or "admin"

    # Handle Human Rejection
    if payload.decision.upper() == "REJECTED":
        await update_approval_status(approval_id, "REJECTED", decided_by)
        await log_audit_event(
            action_id=approval["action_id"],
            tool="gateway",
            operation="approval_decision",
            decision="REJECTED",
            user_id=decided_by,
            details={"approval_id": approval_id, "reason": payload.reason or "Human rejected action"},
        )
        return {"message": "Action successfully rejected by reviewer", "status": "REJECTED"}

    # Resolve human username if JWT token was passed
    if not payload.decided_by and request and hasattr(request.state, "user") and request.state.user:
        try:
            from Dbhelper.user_db_helper import get_user_by_id
            u = await get_user_by_id(request.state.user)
            if u and u.get("username"):
                decided_by = u["username"]
        except Exception:
            pass

    # Handle Human Approval -> MUST RE-VALIDATE!
    if payload.decision.upper() == "APPROVED":
        raw_payload = approval.get("action_payload")
        action_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        action = ToolAction.model_validate(action_data)

        flow_id = await classify_flow(action.tool, action.operation)

        # RE-VALIDATION AGAINST CURRENT ACTIVE POLICIES
        reval = await evaluate_action_policy(action, flow_id)
        if reval.decision == DecisionEnum.BLOCK:
            # Policy changed to BLOCK during waiting period!
            await update_approval_status(approval_id, "REJECTED", decided_by)
            await log_audit_event(
                action_id=str(action.action_id),
                tool=action.tool,
                operation=action.operation,
                flow_id=flow_id,
                decision="BLOCK",
                user_id=decided_by,
                details={
                    "approval_id": approval_id,
                    "decided_by": decided_by,
                    "revalidation_error": "Policy changed to BLOCK during review period",
                    "reason": reval.reason,
                },
            )
            raise HTTPException(
                status_code=403,
                detail=f"Pre-execution revalidation failed: Active policy now blocks this action ({reval.reason})."
            )

        # Revalidation passed -> Update approval, log human decision in audit chain, and execute
        await update_approval_status(approval_id, "APPROVED", decided_by)
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id=flow_id,
            decision="APPROVED",
            agent_id=action.agent_id,
            user_id=decided_by,
            matched_rule_id=getattr(reval, "matched_rule_id", None),
            details={
                "approval_id": approval_id,
                "decided_by": decided_by,
                "action": "human_escalation_approval",
                "reason": payload.reason or "Approved by human compliance officer",
            },
        )
        exec_res = await execute_action(action, flow_id)
        return {
            "message": "Action re-validated, approved, and executed successfully",
            "status": "APPROVED",
            "execution": exec_res,
        }

    raise HTTPException(status_code=400, detail="Invalid decision. Must be 'APPROVED' or 'REJECTED'")


async def get_audit_trail_handler(
    limit: int = Query(50, ge=1, le=500),
    action_id: Optional[str] = Query(None),
):
    """Retrieves immutable, hash-chained audit events with policy explainability."""
    trail = await get_audit_trail(limit=limit, action_id=action_id)
    return {"total": len(trail), "events": trail}


async def verify_audit_integrity_handler():
    """Validates the SHA-256 cryptographic chain of all audit events to prove tamper-evidence."""
    is_valid, issues = await verify_audit_chain_integrity()
    return {
        "status": "TAMPER_FREE" if is_valid else "TAMPER_DETECTED",
        "is_valid": is_valid,
        "chain_issues": issues,
    }


async def list_flows_handler():
    """Lists registered flows in flow_registry."""
    flows = await list_flows()
    return {"total": len(flows), "flows": flows}


async def register_flow_handler(payload: FlowRegistrationRequest):
    """Registers or updates a deterministic flow classification."""
    success = await register_flow(
        tool=payload.tool,
        operation=payload.operation,
        flow_id=payload.flow_id,
        description=payload.description,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to register flow")
    return {"message": f"Flow '{payload.flow_id}' registered for {payload.tool}:{payload.operation}"}
