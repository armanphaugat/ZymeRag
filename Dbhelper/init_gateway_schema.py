import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text

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

def split_sql(sql_content: str):
    clean_lines = []
    for line in sql_content.splitlines():
        idx = line.find("--")
        if idx != -1:
            line = line[:idx]
        clean_lines.append(line)
    clean_sql = "\n".join(clean_lines)

    statements = []
    current_stmt = []
    in_do_block = False

    for line in clean_sql.splitlines():
        if "DO 8649" in line or "DO $" in line:
            in_do_block = True
        current_stmt.append(line)
        if "END 8649" in line or "END $" in line:
            in_do_block = False

        if ";" in line and not in_do_block:
            full_stmt = "\n".join(current_stmt).strip()
            if full_stmt:
                statements.append(full_stmt)
            current_stmt = []

    if current_stmt:
        rem = "\n".join(current_stmt).strip()
        if rem:
            statements.append(rem)

    return [s for s in statements if s.strip("; \n")]

async def init_schema():
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    sql_content = schema_path.read_text(encoding="utf-8")
    statements = split_sql(sql_content)

    print(f"Applying {len(statements)} schema statements to Supabase/Postgres...")
    for stmt in statements:
        try:
            async with AsyncDB() as session:
                await session.execute(text(stmt))
                await session.commit()
        except Exception as e:
            stmt_prev = stmt[:60].replace("\n", " ")
            print(f"Note executing statement: {e} | Summary: {stmt_prev}...")

    print("Schema tables successfully initialized.")

    print("Seeding initial flow_registry entries...")
    async with AsyncDB() as session:
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