from typing import Optional, Dict, Any, List
from sqlalchemy import text
from Dbhelper.db import AsyncDB


async def classify_flow(tool: str, operation: str) -> str:
    """
    Deterministic flow classifier.
    Queries the flow_registry table for an exact match on (tool, operation).
    If no exact match is found, returns 'unclassified'.
    STRICTLY ZERO LLM.
    """
    if not tool or not operation:
        return "unclassified"

    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT flow_id
                    FROM flow_registry
                    WHERE tool = :tool AND operation = :operation
                """),
                {"tool": tool.strip().lower(), "operation": operation.strip().lower()},
            )
            row = result.fetchone()
            if row and row[0]:
                return row[0]
            return "unclassified"
    except Exception as e:
        print(f"[Classifier] Error looking up flow for ({tool}, {operation}): {e}")
        return "unclassified"


async def register_flow(tool: str, operation: str, flow_id: str, description: Optional[str] = None) -> bool:
    """Registers or updates a tool/operation mapping in flow_registry."""
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    INSERT INTO flow_registry (tool, operation, flow_id, description)
                    VALUES (:tool, :op, :flow_id, :desc)
                    ON CONFLICT (tool, operation) DO UPDATE
                    SET flow_id = EXCLUDED.flow_id, description = EXCLUDED.description
                """),
                {
                    "tool": tool.strip().lower(),
                    "op": operation.strip().lower(),
                    "flow_id": flow_id.strip(),
                    "desc": description,
                },
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"[Classifier] Error registering flow ({tool}, {operation}): {e}")
        return False


async def list_flows() -> List[Dict[str, Any]]:
    """Lists all registered flows."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("SELECT tool, operation, flow_id, description FROM flow_registry ORDER BY tool, operation")
            )
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"[Classifier] Error listing flows: {e}")
        return []
