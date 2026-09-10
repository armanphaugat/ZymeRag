import uuid
from Backend.Gateway.audit import log_audit_event
from typing import Optional, Dict, Any
from fastapi import HTTPException, Query, Request
from pydantic import BaseModel
from Dbhelper.rules_db_helper import (
    get_rules,
    get_rule_by_id,
    approve_rule,
    reject_rule,
    update_rule,
)


class UpdateRuleRequest(BaseModel):
    scope: Optional[Dict[str, Any]] = None
    condition: Optional[Dict[str, Any]] = None
    effect: Optional[str] = None
    required_approval_role: Optional[str] = None


class ApproveRuleRequest(BaseModel):
    approved_by: Optional[str] = None


async def list_rules_handler(status: Optional[str] = Query(None, description="Filter rules by status: DRAFT, APPROVED, REJECTED")):
    """List rules, optionally filtered by status (defaults to all)."""
    try:
        rules = await get_rules(status)
        return {"total": len(rules), "rules": rules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_rule_handler(rule_id: str):
    """Retrieve details of a specific rule."""
    rule = await get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


async def approve_rule_handler(rule_id: str, payload: Optional[ApproveRuleRequest] = None, request: Request = None):
    """Approve a draft rule, transitioning status to APPROVED and incrementing version."""
    rule = await get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    user = None
    if request and hasattr(request.state, "user"):
        user = request.state.user
    if not user and payload and payload.approved_by:
        user = payload.approved_by
    approver = user or "admin"

    success = await approve_rule(rule_id, approved_by=approver)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to approve rule")

    updated_rule = await get_rule_by_id(rule_id)
    try:
        await log_audit_event(
            action_id=str(uuid.uuid4()),
            tool="policy_engine",
            operation="approve_rule",
            decision="RULE_APPROVED",
            user_id=approver,
            matched_rule_id=rule_id,
            details={
                "rule_id": rule_id,
                "rule_name": rule.get("name"),
                "approved_by": approver,
                "version": updated_rule.get("version") if updated_rule else 1,
            },
        )
    except Exception as e:
        print(f"[RulesController] Audit log failed: {e}")

    return {"message": "Rule approved successfully", "rule": updated_rule}


async def reject_rule_handler(rule_id: str):
    """Reject a rule, transitioning status to REJECTED."""
    rule = await get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    success = await reject_rule(rule_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reject rule")

    return {"message": f"Rule {rule_id} rejected successfully"}


async def patch_rule_handler(rule_id: str, payload: UpdateRuleRequest):
    """Edit scope, condition, effect, or required role of a draft rule before approval."""
    rule = await get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    success = await update_rule(rule_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update rule")

    updated_rule = await get_rule_by_id(rule_id)
    return {"message": "Rule updated successfully", "rule": updated_rule}
