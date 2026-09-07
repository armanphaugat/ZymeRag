from typing import Optional, Tuple
from sqlalchemy import text
from Dbhelper.db import AsyncDB


async def get_idempotent_result(key: str) -> Optional[str]:
    """Retrieves existing result_id for an idempotency key if present."""
    if not key:
        return None
    try:
        async with AsyncDB() as session:
            row = (
                await session.execute(
                    text("SELECT result_id FROM idempotency_keys WHERE key = :key"),
                    {"key": key},
                )
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"Error checking idempotency key {key}: {e}")
        return None


async def save_idempotent_result(key: str, result_id: str) -> bool:
    """Inserts or updates the result_id for a given idempotency key."""
    if not key:
        return False
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("""
                    INSERT INTO idempotency_keys (key, result_id)
                    VALUES (:key, :result_id)
                    ON CONFLICT (key) DO UPDATE SET result_id = EXCLUDED.result_id
                """),
                {"key": key, "result_id": str(result_id)},
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"Error saving idempotency key {key}: {e}")
        return False


async def remove_idempotent_key(key: str) -> bool:
    """Removes an idempotency key if an operation fails."""
    if not key:
        return False
    try:
        async with AsyncDB() as session:
            await session.execute(
                text("DELETE FROM idempotency_keys WHERE key = :key"),
                {"key": key},
            )
            await session.commit()
            return True
    except Exception as e:
        print(f"Error removing idempotency key {key}: {e}")
        return False
