import logging
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from Dbhelper.db import AsyncDB

logger = logging.getLogger(__name__)


async def link_user_to_content(user_id: str, content_id: str) -> bool:
    """Map a user to a document content record (feed_id = NULL). Idempotent via ON CONFLICT DO NOTHING."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    INSERT INTO user_mappings (user_id, content_id)
                    VALUES (:uid, :cid)
                    ON CONFLICT DO NOTHING
                """),
                {"uid": user_id, "cid": content_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error linking user_id=%s to content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error linking user_id=%s to content_id=%s", user_id, content_id)
        return False


async def link_user_to_feed(user_id: str, feed_id: str) -> bool:
    """Map a user to a website feed record (content_id = NULL). Idempotent via ON CONFLICT DO NOTHING."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    INSERT INTO user_mappings (user_id, feed_id)
                    VALUES (:uid, :fid)
                    ON CONFLICT DO NOTHING
                """),
                {"uid": user_id, "fid": feed_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error linking user_id=%s to feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error linking user_id=%s to feed_id=%s", user_id, feed_id)
        return False


async def get_user_mappings(user_id: str) -> List[dict]:
    """Fetch all content and feed mappings for a user."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("SELECT * FROM user_mappings WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error fetching mappings for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error fetching mappings for user_id=%s", user_id)
        return []


async def get_user_content_ids(user_id: str) -> List[str]:
    """Fetch the content_ids a user is mapped to (excludes feed-only mapping rows)."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("""
                        SELECT content_id FROM user_mappings
                        WHERE user_id = :uid AND content_id IS NOT NULL
                    """),
                    {"uid": user_id},
                )
            ).mappings().all()
            return [r["content_id"] for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error fetching content_ids for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error fetching content_ids for user_id=%s", user_id)
        return []


async def get_user_feed_ids(user_id: str) -> List[str]:
    """Fetch the feed_ids a user is mapped to (excludes content-only mapping rows)."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("""
                        SELECT feed_id FROM user_mappings
                        WHERE user_id = :uid AND feed_id IS NOT NULL
                    """),
                    {"uid": user_id},
                )
            ).mappings().all()
            return [r["feed_id"] for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error fetching feed_ids for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error fetching feed_ids for user_id=%s", user_id)
        return []


async def get_users_for_content(content_id: str) -> List[str]:
    """Reverse lookup: fetch the user_ids mapped to a given content_id."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("SELECT user_id FROM user_mappings WHERE content_id = :cid"),
                    {"cid": content_id},
                )
            ).mappings().all()
            return [r["user_id"] for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error fetching users for content_id=%s", content_id)
        return []
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error fetching users for content_id=%s", content_id)
        return []


async def get_users_for_feed(feed_id: str) -> List[str]:
    """Reverse lookup: fetch the user_ids mapped to a given feed_id."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("SELECT user_id FROM user_mappings WHERE feed_id = :fid"),
                    {"fid": feed_id},
                )
            ).mappings().all()
            return [r["user_id"] for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error fetching users for feed_id=%s", feed_id)
        return []
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error fetching users for feed_id=%s", feed_id)
        return []


async def user_has_content_mapping(user_id: str, content_id: str) -> bool:
    """Check whether a user-content mapping already exists."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("""
                        SELECT 1 FROM user_mappings
                        WHERE user_id = :uid AND content_id = :cid
                    """),
                    {"uid": user_id, "cid": content_id},
                )
            ).first()
            return row is not None
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error checking mapping user_id=%s, content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error checking mapping user_id=%s, content_id=%s", user_id, content_id)
        return False


async def user_has_feed_mapping(user_id: str, feed_id: str) -> bool:
    """Check whether a user-feed mapping already exists."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("""
                        SELECT 1 FROM user_mappings
                        WHERE user_id = :uid AND feed_id = :fid
                    """),
                    {"uid": user_id, "fid": feed_id},
                )
            ).first()
            return row is not None
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error checking mapping user_id=%s, feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error checking mapping user_id=%s, feed_id=%s", user_id, feed_id)
        return False


async def count_user_mappings(user_id: str) -> int:
    """Return the total number of mappings (content + feed) for a user."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT COUNT(*) AS cnt FROM user_mappings WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            ).mappings().first()
            return int(row["cnt"]) if row else 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error counting mappings for user_id=%s", user_id)
        return 0
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error counting mappings for user_id=%s", user_id)
        return 0


async def unlink_user_from_content(user_id: str, content_id: str) -> bool:
    """Remove a single user-content mapping."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    DELETE FROM user_mappings
                    WHERE user_id = :uid AND content_id = :cid
                """),
                {"uid": user_id, "cid": content_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error unlinking user_id=%s from content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error unlinking user_id=%s from content_id=%s", user_id, content_id)
        return False


async def unlink_user_from_feed(user_id: str, feed_id: str) -> bool:
    """Remove a single user-feed mapping."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    DELETE FROM user_mappings
                    WHERE user_id = :uid AND feed_id = :fid
                """),
                {"uid": user_id, "fid": feed_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error unlinking user_id=%s from feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error unlinking user_id=%s from feed_id=%s", user_id, feed_id)
        return False


async def delete_all_user_mappings(user_id: str) -> bool:
    """Remove all mappings (content and feed) for a user. Returns True if at least one row was deleted."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("DELETE FROM user_mappings WHERE user_id = :uid"),
                {"uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_mapping_db_helper] Database error deleting all mappings for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_mapping_db_helper] Unexpected error deleting all mappings for user_id=%s", user_id)
        return False