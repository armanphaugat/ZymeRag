import logging
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from Dbhelper.db import AsyncDB

logger = logging.getLogger(__name__)


async def save_website_to_database(
    url: str,
    feed_id: str,
    chunks: int = 0,
) -> bool:
    """Save website feed record to feeds table. Returns True if created successfully."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    INSERT INTO feeds (feed_id, url, chunks)
                    VALUES (:fid, :url, :chunks)
                    ON CONFLICT (feed_id) DO NOTHING
                """),
                {"fid": feed_id, "url": url, "chunks": chunks},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[website_db_helper] Database error saving website %s (feed_id: %s)", url, feed_id)
        return False
    except Exception:
        logger.exception("[website_db_helper] Unexpected error saving website %s (feed_id: %s)", url, feed_id)
        return False


async def get_urls_from_database() -> List[Tuple[str, str]]:
    """Fetch all active website URLs and feed_ids."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    SELECT url, feed_id
                    FROM feeds
                    WHERE deleted_at IS NULL
                """)
            )
            rows = result.fetchall()
            return [(row[0], row[1]) for row in rows]
    except SQLAlchemyError:
        logger.exception("[website_db_helper] Database error in get_urls_from_database")
        return []
    except Exception:
        logger.exception("[website_db_helper] Unexpected error in get_urls_from_database")
        return []


async def update_website_last_crawled(feed_id: str, chunks: Optional[int] = None) -> bool:
    """Update website updated_at timestamp, and optionally update chunk count if provided."""
    try:
        async with AsyncDB() as s:
            if chunks is not None:
                result = await s.execute(
                    text("""
                        UPDATE feeds
                        SET chunks = :chunks, updated_at = NOW()
                        WHERE feed_id = :fid AND deleted_at IS NULL
                    """),
                    {"chunks": chunks, "fid": feed_id},
                )
            else:
                result = await s.execute(
                    text("""
                        UPDATE feeds
                        SET updated_at = NOW()
                        WHERE feed_id = :fid AND deleted_at IS NULL
                    """),
                    {"fid": feed_id},
                )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[website_db_helper] Database error in update_website_last_crawled feed_id=%s", feed_id)
        return False
    except Exception:
        logger.exception("[website_db_helper] Unexpected error in update_website_last_crawled feed_id=%s", feed_id)
        return False


async def get_feed_by_id(feed_id: str) -> Optional[dict]:
    """Fetch a single active feed record by feed_id."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM feeds WHERE feed_id = :fid AND deleted_at IS NULL"),
                    {"fid": feed_id},
                )
            ).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError:
        logger.exception("[website_db_helper] Database error retrieving feed with feed_id %s", feed_id)
        return None
    except Exception:
        logger.exception("[website_db_helper] Unexpected error retrieving feed with feed_id %s", feed_id)
        return None


async def delete_website_from_database(feed_id: str) -> bool:
    """Soft-delete a website feed record by setting deleted_at."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("UPDATE feeds SET deleted_at = NOW() WHERE feed_id = :fid AND deleted_at IS NULL"),
                {"fid": feed_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[website_db_helper] Database error soft deleting website feed_id=%s", feed_id)
        return False
    except Exception:
        logger.exception("[website_db_helper] Unexpected error soft deleting website feed_id=%s", feed_id)
        return False