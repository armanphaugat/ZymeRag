from typing import Optional, List, Tuple
from sqlalchemy import text
from Dbhelper.db import AsyncDB
from Dbhelper.pdf_db_helper import save_content_to_database as save_pdf_to_database  # Alias for backward compatibility


async def save_website_to_database(
    url: str,
    id: str,
    server_id: str = "default",
    uploaded_by: str = "system",
    username: str = "system",
) -> bool:
    try:
        async with AsyncDB() as s:
            # Ensure server exists if foreign keys are enabled
            await s.execute(
                text("INSERT INTO servers (server_id, server_name) VALUES (:sid, :name) ON CONFLICT DO NOTHING"),
                {"sid": str(server_id), "name": f"Server-{server_id}"},
            )

            # Insert upload record with feed_id
            await s.execute(
                text("""
                    INSERT INTO uploads
                        (server_id, uploaded_by, username, type, name, feed_id, status)
                    VALUES
                        (:sid, :uid, :uname, 'website', :name, :fid, 'ok')
                """),
                {
                    "sid": str(server_id),
                    "uid": str(uploaded_by),
                    "uname": username,
                    "name": url,
                    "fid": id,
                },
            )

            # Insert into server_feeds
            await s.execute(
                text("""
                    INSERT INTO server_feeds (server_id, feed_id)
                    VALUES (:sid, :fid)
                """),
                {"sid": str(server_id), "fid": id},
            )
            await s.commit()
            return True
    except Exception as e:
        print(f"Error saving website {url} (feed_id: {id}) to Supabase DB: {e}")
        return False


async def get_urls_from_database() -> List[Tuple[str, str]]:
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    SELECT name AS url, feed_id
                    FROM uploads
                    WHERE type = 'website' AND feed_id IS NOT NULL AND status = 'ok' AND deleted_at IS NULL
                """)
            )
            rows = result.fetchall()
            return [(row[0], row[1]) for row in rows]
    except Exception as e:
        print(f"Error fetching website URLs from Supabase DB: {e}")
        return []


async def update_website_last_crawled(id: str, status: str = "ok") -> bool:
    try:
        async with AsyncDB() as s:
            await s.execute(
                text("UPDATE uploads SET status = :status WHERE feed_id = :fid"),
                {"status": status, "fid": id},
            )
            await s.commit()
            return True
    except Exception as e:
        print(f"Error updating website feed_id {id}: {e}")
        return False


async def delete_website_from_database(id: str) -> bool:
    try:
        async with AsyncDB() as s:
            await s.execute(
                text("UPDATE uploads SET deleted_at = NOW(), status = 'failed' WHERE feed_id = :fid"),
                {"fid": id},
            )
            await s.commit()
            return True
    except Exception as e:
        print(f"Error soft deleting website with feed_id {id}: {e}")
        return False