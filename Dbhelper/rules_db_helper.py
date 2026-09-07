import json
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from Dbhelper.db import AsyncDB


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
    """Inserts a new rule into the rules table."""
    rule_id = str(uuid.uuid4())
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
                    "status": status.upper(),
                    "approved_by": approved_by,
                },
            )
            await session.commit()
            return rule_id
    except Exception as e:
        print(f"Error saving rule: {e}")
        return None


async def get_rules(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves rules, optionally filtered by status (DRAFT, APPROVED, REJECTED)."""
    try:
        async with AsyncDB() as session:
            query = """
                SELECT r.rule_id, r.version, r.scope, r.condition, r.effect,
                       r.required_approval_role, r.source_document, r.source_chunk,
                       r.source_clause, r.status, r.approved_by, r.approved_at, r.created_at,
                       u.name as document_name
                FROM rules r
                LEFT JOIN uploads u ON r.source_document = u.content_id
            """
            params = {}
            if status:
                query += " WHERE r.status = :status"
                params["status"] = status.upper()
            query += " ORDER BY r.created_at DESC"

            result = await session.execute(text(query), params)
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"Error retrieving rules: {e}")
        return []


async def get_rule_by_id(rule_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single rule by rule_id."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT rule_id, version, scope, condition, effect,
                           required_approval_role, source_document, source_chunk,
                           source_clause, status, approved_by, approved_at, created_at
                    FROM rules
                    WHERE rule_id = :rule_id
                """),
                {"rule_id": rule_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception as e:
        print(f"Error retrieving rule {rule_id}: {e}")
        return None


async def approve_rule(rule_id: str, approved_by: str = "admin") -> bool:
    """Approves a DRAFT rule and increments its version."""
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    UPDATE rules
                    SET status = 'APPROVED',
                        approved_by = :approved_by,
                        approved_at = now(),
                        version = version + 1
                    WHERE rule_id = :rule_id
                """),
                {"rule_id": rule_id, "approved_by": approved_by},
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"Error approving rule {rule_id}: {e}")
        return False


async def reject_rule(rule_id: str) -> bool:
    """Sets a rule status to REJECTED."""
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("UPDATE rules SET status = 'REJECTED' WHERE rule_id = :rule_id"),
                {"rule_id": rule_id},
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"Error rejecting rule {rule_id}: {e}")
        return False


async def update_rule(rule_id: str, updates: Dict[str, Any]) -> bool:
    """Updates fields (scope, condition, effect, role) of a draft rule."""
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
        return False

    sql = f"UPDATE rules SET {', '.join(set_clauses)} WHERE rule_id = :rule_id"
    try:
        async with AsyncDB() as session:
            await session.execute(text(sql), params)
            await session.commit()
            return True
    except Exception as e:
        print(f"Error updating rule {rule_id}: {e}")
        return False


async def get_approved_rules_for_action(flow_id: str, tool: str, operation: str) -> List[Dict[str, Any]]:
    """
    Retrieves all APPROVED rules matching the given flow_id, tool, and operation.
    Rules can match specific values or wildcard/omitted keys.
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
                {"flow_id": flow_id, "tool": tool, "op": operation},
            )
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"Error querying approved rules for ({flow_id}, {tool}, {operation}): {e}")
        return []
