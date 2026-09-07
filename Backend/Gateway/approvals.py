import json
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from Dbhelper.db import AsyncDB
from Backend.Gateway.schemas import ToolAction, DecisionEnum, ExecutionResult


async def create_pending_approval(
    action: ToolAction,
    rule_id: Optional[str],
    required_role: str = "admin"
) -> str:
    """Creates a PENDING approval record for an escalated action."""
    approval_id = str(uuid.uuid4())
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    INSERT INTO approvals
                        (approval_id, action_id, rule_id, action_payload, required_role, status)
                    VALUES
                        (:aid, :act_id, :rid, :payload, :role, 'PENDING')
                """),
                {
                    "aid": approval_id,
                    "act_id": str(action.action_id),
                    "rid": rule_id,
                    "payload": json.dumps(action.model_dump(), default=str),
                    "role": required_role,
                },
            )
            await session.commit()
            return approval_id
    except Exception as e:
        print(f"[Approvals] Error creating pending approval: {e}")
        return approval_id


async def list_pending_approvals(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all PENDING approvals, optionally filtered by required_role."""
    try:
        async with AsyncDB() as session:
            query = """
                SELECT a.approval_id, a.action_id, a.rule_id, a.action_payload,
                       a.required_role, a.status, a.created_at,
                       r.source_clause, r.scope, r.condition
                FROM approvals a
                LEFT JOIN rules r ON a.rule_id = r.rule_id
                WHERE a.status = 'PENDING'
            """
            params = {}
            if role:
                query += " AND a.required_role = :role"
                params["role"] = role
            query += " ORDER BY a.created_at DESC"

            result = await session.execute(text(query), params)
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"[Approvals] Error listing approvals: {e}")
        return []


async def get_approval_by_id(approval_id: str) -> Optional[Dict[str, Any]]:
    """Fetches an approval record by its ID."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("SELECT * FROM approvals WHERE approval_id = :aid"),
                {"aid": approval_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception as e:
        print(f"[Approvals] Error retrieving approval {approval_id}: {e}")
        return None


async def update_approval_status(
    approval_id: str,
    status: str,
    decided_by: str = "admin"
) -> bool:
    """Updates approval status to APPROVED or REJECTED."""
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    UPDATE approvals
                    SET status = :status,
                        decided_by = :decided_by,
                        decided_at = now()
                    WHERE approval_id = :aid
                """),
                {"status": status.upper(), "decided_by": decided_by, "aid": approval_id},
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"[Approvals] Error updating approval status: {e}")
        return False
