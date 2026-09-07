import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Dbhelper.db import AsyncDB, engine


DEFAULT_FLOWS = [
    ("crm", "get_customer", "crm_read", "Read customer details from CRM"),
    ("crm", "update_customer", "crm_write", "Modify customer records in CRM"),
    ("crm", "delete_customer", "crm_delete", "Delete customer records from CRM"),
    ("payment", "transfer_funds", "payment_transfer", "Transfer funds to an account"),
    ("payment", "refund_payment", "payment_refund", "Issue a payment refund"),
    ("email", "send_email", "email_notification", "Dispatch an email via mail gateway"),
]


async def init_schema():
    """Reads schema.sql and applies all DDL statements to the connected Postgres database."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    sql_content = schema_path.read_text(encoding="utf-8")
    
    # Split queries by semicolon to execute individually
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    print(f"Applying {len(statements)} schema statements to Supabase/Postgres...")
    async with AsyncDB() as session:
        for stmt in statements:
            try:
                await session.execute(text(stmt))
            except Exception as e:
                print(f"Warning executing statement: {e}\nStatement: {stmt[:60]}...")
        await session.commit()
        print("Schema tables successfully initialized.")

        # Seed default flow_registry rows
        print("Seeding initial flow_registry entries...")
        for tool, op, flow_id, desc in DEFAULT_FLOWS:
            await session.execute(
                text("""
                    INSERT INTO flow_registry (tool, operation, flow_id, description)
                    VALUES (:tool, :op, :flow_id, :desc)
                    ON CONFLICT (tool, operation) DO NOTHING
                """),
                {"tool": tool, "op": op, "flow_id": flow_id, "desc": desc},
            )
        await session.commit()
        print("Default flow registry seeded successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(init_schema())
    except Exception as exc:
        print(f"Failed to initialize schema: {exc}", file=sys.stderr)
        sys.exit(1)
