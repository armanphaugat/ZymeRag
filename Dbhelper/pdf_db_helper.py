from typing import Optional
from sqlalchemy import text
from Dbhelper.db import AsyncDB


async def save_content_to_database(
    name: str,
    id: str,
    server_id: str = "default",
    uploaded_by: str = "system",
    username: str = "system",
    doc_type: str = "document",
) -> bool:
    try:
        async with AsyncDB() as s:
            # Ensure server exists if foreign keys are enabled
            await s.execute(
                text("INSERT INTO servers (server_id, server_name) VALUES (:sid, :name) ON CONFLICT DO NOTHING"),
                {"sid": str(server_id), "name": f"Server-{server_id}"},
            )

            # Insert/Log upload
            await s.execute(
                text("""
                    INSERT INTO uploads
                        (server_id, uploaded_by, username, type, name, content_id, status)
                    VALUES
                        (:sid, :uid, :uname, :type, :name, :cid, 'ok')
                """),
                {
                    "sid": str(server_id),
                    "uid": str(uploaded_by),
                    "uname": username,
                    "type": doc_type,
                    "name": name,
                    "cid": id,
                },
            )

            # Insert into server_uploads
            await s.execute(
                text("""
                    INSERT INTO server_uploads (server_id, content_id)
                    VALUES (:sid, :cid)
                """),
                {"sid": str(server_id), "cid": id},
            )
            await s.commit()
            return True
    except Exception as e:
        print(f"Error saving content {name} (content_id: {id}) to Supabase DB: {e}")
        return False


async def get_document_by_id(id: str) -> Optional[dict]:
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM uploads WHERE content_id = :cid AND deleted_at IS NULL"),
                    {"cid": id},
                )
            ).mappings().first()
            return dict(row) if row else None
    except Exception as e:
        print(f"Error retrieving document with content_id {id}: {e}")
        return None


async def delete_content_from_database(id: str) -> bool:
    try:
        async with AsyncDB() as s:
            await s.execute(
                text("UPDATE uploads SET deleted_at = NOW(), status = 'failed' WHERE content_id = :cid"),
                {"cid": id},
            )
            await s.commit()
            return True
    except Exception as e:
        print(f"Error soft deleting document with content_id {id}: {e}")
        return False