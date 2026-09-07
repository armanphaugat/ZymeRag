import hashlib
import json
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import text
from Dbhelper.db import AsyncDB

GENESIS_HASH = "0" * 64


def compute_event_hash(prev_hash: str, canonical_payload: Dict[str, Any]) -> str:
    """Computes SHA-256 hash chaining prev_hash with canonical json string."""
    serialized = json.dumps(canonical_payload, sort_keys=True, default=str)
    raw = f"{prev_hash}|{serialized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_latest_audit_hash() -> str:
    """Fetches the curr_hash of the most recently inserted audit event."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("SELECT curr_hash FROM audit_events ORDER BY created_at DESC LIMIT 1")
            )
            row = result.fetchone()
            return row[0] if row and row[0] else GENESIS_HASH
    except Exception as e:
        print(f"[Audit] Error fetching latest audit hash: {e}")
        return GENESIS_HASH


async def log_audit_event(
    action_id: str,
    tool: str,
    operation: str,
    decision: str,
    flow_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    matched_rule_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Logs an audit event into audit_events using cryptographic SHA-256 hash chaining.
    Every evaluation, execution, escalation, or rejection path must call this function.
    """
    event_id = str(uuid.uuid4())
    prev_hash = await get_latest_audit_hash()
    
    details_data = details or {}
    canonical = {
        "event_id": event_id,
        "action_id": str(action_id),
        "tool": tool,
        "operation": operation,
        "flow_id": flow_id,
        "decision": decision,
        "matched_rule_id": str(matched_rule_id) if matched_rule_id else None,
        "agent_id": agent_id,
        "user_id": user_id,
        "details": details_data,
    }
    curr_hash = compute_event_hash(prev_hash, canonical)

    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    INSERT INTO audit_events
                        (event_id, action_id, agent_id, user_id, tool, operation,
                         flow_id, matched_rule_id, decision, details, prev_hash, curr_hash)
                    VALUES
                        (:event_id, :action_id, :agent_id, :user_id, :tool, :operation,
                         :flow_id, :matched_rule_id, :decision, :details, :prev_hash, :curr_hash)
                """),
                {
                    "event_id": event_id,
                    "action_id": str(action_id),
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "tool": tool,
                    "operation": operation,
                    "flow_id": flow_id,
                    "matched_rule_id": str(matched_rule_id) if matched_rule_id else None,
                    "decision": decision.upper(),
                    "details": json.dumps(details_data, default=str),
                    "prev_hash": prev_hash,
                    "curr_hash": curr_hash,
                },
            )
            await session.commit()
            return event_id
    except Exception as e:
        print(f"[Audit] Critical: Failed to write audit event: {e}")
        return event_id


async def get_audit_trail(
    limit: int = 50,
    action_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves audit logs joined with rules and policy_chunks to expose
    source_clause and justify policy decisions.
    """
    try:
        async with AsyncDB() as session:
            query = """
                SELECT a.event_id, a.action_id, a.agent_id, a.user_id, a.tool,
                       a.operation, a.flow_id, a.decision, a.details, a.prev_hash,
                       a.curr_hash, a.created_at,
                       r.rule_id, r.source_clause, r.required_approval_role,
                       u.name as policy_document_name
                FROM audit_events a
                LEFT JOIN rules r ON a.matched_rule_id = r.rule_id
                LEFT JOIN uploads u ON r.source_document = u.content_id
            """
            params = {"limit": limit}
            if action_id:
                query += " WHERE a.action_id = :action_id"
                params["action_id"] = str(action_id)
            query += " ORDER BY a.created_at DESC LIMIT :limit"

            result = await session.execute(text(query), params)
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"[Audit] Error retrieving audit trail: {e}")
        return []


async def verify_audit_chain_integrity() -> Tuple[bool, List[str]]:
    """
    Traverses the audit_events table chronologically and validates each SHA-256 hash link.
    Returns (is_valid: bool, issues: List[str]).
    """
    issues = []
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("SELECT * FROM audit_events ORDER BY created_at ASC")
            )
            rows = [dict(r) for r in result.mappings().fetchall()]

        if not rows:
            return True, ["Audit log is empty (valid)"]

        expected_prev = GENESIS_HASH
        for idx, row in enumerate(rows):
            actual_prev = row.get("prev_hash")
            actual_curr = row.get("curr_hash")

            if actual_prev != expected_prev:
                issues.append(
                    f"Broken link at event {row.get('event_id')} (index {idx}): "
                    f"expected prev_hash {expected_prev}, found {actual_prev}"
                )

            canonical = {
                "event_id": str(row.get("event_id")),
                "action_id": str(row.get("action_id")),
                "tool": row.get("tool"),
                "operation": row.get("operation"),
                "flow_id": row.get("flow_id"),
                "decision": row.get("decision"),
                "matched_rule_id": str(row.get("matched_rule_id")) if row.get("matched_rule_id") else None,
                "agent_id": row.get("agent_id"),
                "user_id": row.get("user_id"),
                "details": row.get("details") if isinstance(row.get("details"), dict) else json.loads(row.get("details") or "{}"),
            }
            recomputed = compute_event_hash(actual_prev, canonical)
            if recomputed != actual_curr:
                issues.append(
                    f"Hash mismatch at event {row.get('event_id')} (index {idx}): "
                    f"recomputed {recomputed} != recorded {actual_curr}"
                )

            expected_prev = actual_curr

        is_valid = len(issues) == 0
        return is_valid, issues
    except Exception as e:
        return False, [f"Integrity check failed with error: {e}"]
