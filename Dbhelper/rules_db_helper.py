import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from Dbhelper.db import AsyncDB

logger = logging.getLogger(__name__)


async def save_rule(
    scope: dict,
    condition: dict,
    effect: str,
    required_approval_role: Optional[str] = None,
    source_document: Optional[str] = None,
    source_chunk: Optional[str] = None,
    source_clause: Optional[str] = None,
    status: str = "DRAFT",
    approved_by: Optional[str] = None,
) -> Optional[str]:
    """
    Inserts a new rule into the rules table.
    Crucial Guarantee: All extracted rules ALWAYS start with status = 'DRAFT'.
    """
    rule_id = str(uuid.uuid4())
    # Force DRAFT on creation for human governance lifecycle
    enforced_status = "DRAFT" if approved_by is None else status.upper()

    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    INSERT INTO rules
                        (rule_id, version, scope, condition, effect, required_approval_role,
                         source_document, source_chunk, source_clause, status, approved_by)
                    VALUES
                        (:rule_id, 1, :scope, :condition, :effect, :required_approval_role,
                         :source_document, :source_chunk, :source_clause, :status, :approved_by)
                """),
                {
                    "rule_id": rule_id,
                    "scope": json.dumps(scope),
                    "condition": json.dumps(condition),
                    "effect": effect.upper(),
                    "required_approval_role": required_approval_role,
                    "source_document": source_document,
                    "source_chunk": source_chunk,
                    "source_clause": source_clause,
                    "status": enforced_status,
                    "approved_by": approved_by,
                },
            )
            await session.commit()
            return rule_id
    except Exception as e:
        logger.error(f"Error saving rule: {e}")
        return None


async def get_rules(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves rules, optionally filtered by status (DRAFT, APPROVED, REJECTED).
    Includes relational provenance from policy_chunks (page_number, section_heading).
    """
    try:
        async with AsyncDB() as session:
            query = """
                SELECT r.rule_id, r.version, r.scope, r.condition, r.effect,
                       r.required_approval_role, r.source_document, r.source_chunk,
                       r.source_clause, r.status, r.approved_by, r.approved_at, r.created_at,
                       u.name as document_name,
                       pc.page_number, pc.section_heading
                FROM rules r
                LEFT JOIN contents u ON r.source_document = u.content_id
                LEFT JOIN policy_chunks pc ON r.source_chunk = pc.chunk_id
            """
            params = {}
            if status:
                query += " WHERE r.status = :status"
                params["status"] = status.upper()
            query += " ORDER BY r.created_at DESC"

            result = await session.execute(text(query), params)
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving rules: {e}")
        return []


async def get_rule_by_id(rule_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single rule by rule_id with full relational provenance."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT r.rule_id, r.version, r.scope, r.condition, r.effect,
                           r.required_approval_role, r.source_document, r.source_chunk,
                           r.source_clause, r.status, r.approved_by, r.approved_at, r.created_at,
                           u.name as document_name,
                           pc.page_number, pc.section_heading
                    FROM rules r
                    LEFT JOIN contents u ON r.source_document = u.content_id
                    LEFT JOIN policy_chunks pc ON r.source_chunk = pc.chunk_id
                    WHERE r.rule_id = :rule_id
                """),
                {"rule_id": rule_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving rule {rule_id}: {e}")
        return None


async def approve_rule(rule_id: str, approved_by: str = "admin") -> Tuple[bool, str]:
    """
    Approves a rule with safe, explicit status transitions:
    - Allowed transition: DRAFT -> APPROVED.
    - Safety Guarantee: REJECTED rules CANNOT be approved directly (prevents accidental activation).
    - If already APPROVED, remains APPROVED (idempotent).
    """
    rule = await get_rule_by_id(rule_id)
    if not rule:
        return False, f"Rule {rule_id} not found"

    cur_status = rule.get("status", "").upper()
    if cur_status == "APPROVED":
        return True, "Rule is already approved"

    if cur_status == "REJECTED":
        return False, "Cannot approve a REJECTED rule. Rejected rules cannot become active."

    if cur_status != "DRAFT":
        return False, f"Cannot approve rule with invalid status '{cur_status}'"

    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    UPDATE rules
                    SET status = 'APPROVED',
                        approved_by = :approved_by,
                        approved_at = now(),
                        version = version + 1
                    WHERE rule_id = :rule_id AND status = 'DRAFT'
                """),
                {"rule_id": rule_id, "approved_by": approved_by},
            )
            await session.commit()
            if result.rowcount > 0:
                return True, "Rule approved successfully"
            return False, "Rule status changed concurrently"
    except Exception as e:
        logger.error(f"Error approving rule {rule_id}: {e}")
        return False, str(e)


async def reject_rule(rule_id: str) -> Tuple[bool, str]:
    """
    Rejects a rule with explicit status transition:
    - Allowed transition: DRAFT -> REJECTED.
    - If already REJECTED, returns True.
    - If already APPROVED, fails (approved active rules must be deprecated or deleted through a change procedure).
    """
    rule = await get_rule_by_id(rule_id)
    if not rule:
        return False, f"Rule {rule_id} not found"

    cur_status = rule.get("status", "").upper()
    if cur_status == "REJECTED":
        return True, "Rule is already rejected"

    if cur_status == "APPROVED":
        return False, "Cannot directly reject an APPROVED rule. Archive or create a new policy version."

    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("UPDATE rules SET status = 'REJECTED' WHERE rule_id = :rule_id AND status = 'DRAFT'"),
                {"rule_id": rule_id},
            )
            await session.commit()
            if result.rowcount > 0:
                return True, "Rule rejected successfully"
            return False, "Rule was not in DRAFT status"
    except Exception as e:
        logger.error(f"Error rejecting rule {rule_id}: {e}")
        return False, str(e)


async def update_rule(rule_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Updates fields (scope, condition, effect, role) of a rule.
    Strict Safety Constraint: Can ONLY edit rules while in 'DRAFT' status.
    """
    rule = await get_rule_by_id(rule_id)
    if not rule:
        return False, f"Rule {rule_id} not found"

    cur_status = rule.get("status", "").upper()
    if cur_status != "DRAFT":
        return False, f"Cannot edit rule in '{cur_status}' status. Only DRAFT rules may be edited."

    allowed_fields = {"scope", "condition", "effect", "required_approval_role"}
    set_clauses = []
    params = {"rule_id": rule_id}

    for k, v in updates.items():
        if k in allowed_fields:
            if k in ("scope", "condition") and isinstance(v, (dict, list)):
                set_clauses.append(f"{k} = :{k}")
                params[k] = json.dumps(v)
            else:
                set_clauses.append(f"{k} = :{k}")
                params[k] = v

    if not set_clauses:
        return False, "No valid fields provided to update"

    sql = f"UPDATE rules SET {', '.join(set_clauses)} WHERE rule_id = :rule_id AND status = 'DRAFT'"
    try:
        async with AsyncDB() as session:
            result = await session.execute(text(sql), params)
            await session.commit()
            if result.rowcount > 0:
                return True, "Rule updated successfully"
            return False, "Rule was not in DRAFT status"
    except Exception as e:
        logger.error(f"Error updating rule {rule_id}: {e}")
        return False, str(e)


async def get_approved_rules_for_action(flow_id: str, tool: str, operation: str) -> List[Dict[str, Any]]:
    """
    Retrieves all APPROVED rules matching the given flow_id, tool, and operation.
    CRITICAL SECURITY GUARANTEE:
    Strictly queries `WHERE status = 'APPROVED'`. DRAFT or REJECTED rules are
    guaranteed NEVER to be retrieved or enforced at runtime.
    """
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT rule_id, version, scope, condition, effect,
                           required_approval_role, source_document, source_chunk,
                           source_clause, status, approved_by, approved_at, created_at
                    FROM rules
                    WHERE status = 'APPROVED'
                      AND (scope->>'flow_id' = :flow_id OR scope->>'flow_id' = '*' OR scope->>'flow_id' IS NULL)
                      AND (scope->>'tool' = :tool OR scope->>'tool' = '*' OR scope->>'tool' IS NULL)
                      AND (scope->>'operation' = :operation OR scope->>'operation' = '*' OR scope->>'operation' IS NULL)
                """),
                {"flow_id": flow_id, "tool": tool, "operation": operation},
            )
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        logger.error(f"Error querying approved rules for ({flow_id}, {tool}, {operation}): {e}")
        return []
