from datetime import datetime, timezone
import hashlib
import hmac
import logging
from typing import List, Optional, Union
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from Dbhelper.db import AsyncDB

logger = logging.getLogger(__name__)


def hash_refresh_token(token: str) -> str:
    """Compute SHA-256 hash of a refresh token for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_datetime(dt_input: Union[datetime, str]) -> datetime:
    """Normalize datetime or ISO string to a timezone-aware UTC datetime."""
    if isinstance(dt_input, str):
        cleaned_str = dt_input.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned_str)
    elif isinstance(dt_input, datetime):
        dt = dt_input
    else:
        raise ValueError(f"Invalid datetime input type: {type(dt_input)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ───────────────────────────────────────────────────────────────
#  USER operations — create / read
# ───────────────────────────────────────────────────────────────

async def create_user(
    user_id: str,
    username: str,
    email: Optional[str] = None,
    password_hash: Optional[str] = None,
) -> bool:
    """Insert a new user record. Returns True if created, False if user already exists or failed."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    INSERT INTO users (user_id, username, email, password_hash)
                    VALUES (:uid, :uname, :email, :phash)
                    ON CONFLICT DO NOTHING
                """),
                {"uid": user_id, "uname": username, "email": email, "phash": password_hash},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in create_user for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in create_user for user_id=%s", user_id)
        return False


async def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a single active user by user_id."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM users WHERE user_id = :uid AND is_active = TRUE"),
                    {"uid": user_id},
                )
            ).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in get_user_by_id for user_id=%s", user_id)
        return None
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_by_id for user_id=%s", user_id)
        return None


async def get_user_by_username(username: str) -> Optional[dict]:
    """Fetch a single active user by username."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM users WHERE username = :uname AND is_active = TRUE"),
                    {"uname": username},
                )
            ).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in get_user_by_username for username=%s", username)
        return None
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_by_username for username=%s", username)
        return None


async def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch a single active user by email."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM users WHERE email = :email AND is_active = TRUE"),
                    {"email": email},
                )
            ).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in get_user_by_email for email=%s", email)
        return None
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_by_email for email=%s", email)
        return None


async def user_exists(user_id: str, include_inactive: bool = False) -> bool:
    """Check whether a user_id exists. By default only checks active users."""
    try:
        async with AsyncDB() as s:
            query = "SELECT 1 FROM users WHERE user_id = :uid"
            if not include_inactive:
                query += " AND is_active = TRUE"
            row = (await s.execute(text(query), {"uid": user_id})).first()
            return row is not None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in user_exists for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in user_exists for user_id=%s", user_id)
        return False


async def username_exists(username: str) -> bool:
    """Check whether a username is already taken (active or inactive)."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT 1 FROM users WHERE username = :uname"),
                    {"uname": username},
                )
            ).first()
            return row is not None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in username_exists for username=%s", username)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in username_exists for username=%s", username)
        return False


async def email_exists(email: str) -> bool:
    """Check whether an email is already registered (active or inactive)."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT 1 FROM users WHERE email = :email"),
                    {"email": email},
                )
            ).first()
            return row is not None
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in email_exists for email=%s", email)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in email_exists for email=%s", email)
        return False


async def list_active_users(limit: int = 100, offset: int = 0) -> List[dict]:
    """Fetch a page of active users, ordered by creation date (newest first)."""
    try:
        async with AsyncDB() as s:
            rows = (
                await s.execute(
                    text("""
                        SELECT * FROM users
                        WHERE is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"limit": limit, "offset": offset},
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in list_active_users (limit=%s, offset=%s)", limit, offset)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in list_active_users (limit=%s, offset=%s)", limit, offset)
        return []


async def count_active_users() -> int:
    """Return the total number of active users."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(text("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE"))
            ).mappings().first()
            return int(row["cnt"]) if row else 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in count_active_users")
        return 0
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in count_active_users")
        return 0


# ───────────────────────────────────────────────────────────────
#  USER operations — update
# ───────────────────────────────────────────────────────────────

async def update_username(user_id: str, new_username: str) -> bool:
    """Update a user's username."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET username = :uname, updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"uname": new_username, "uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in update_username for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in update_username for user_id=%s", user_id)
        return False


async def update_email(user_id: str, new_email: str) -> bool:
    """Update a user's email address."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET email = :email, updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"email": new_email, "uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in update_email for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in update_email for user_id=%s", user_id)
        return False


async def update_password_hash(user_id: str, new_password_hash: str) -> bool:
    """Update a user's stored password hash."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET password_hash = :phash, updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"phash": new_password_hash, "uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in update_password_hash for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in update_password_hash for user_id=%s", user_id)
        return False


async def update_refresh_token(
    user_id: str,
    refresh_token: str,
    expires_at: Union[datetime, str],
    hash_token: bool = True,
) -> bool:
    """Update refresh token (hashed by default) and normalized expiry timestamp."""
    try:
        norm_expires = _normalize_datetime(expires_at)
        stored_token = hash_refresh_token(refresh_token) if hash_token else refresh_token

        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET refresh_token = :token,
                        refresh_token_expires_at = :exp,
                        updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"token": stored_token, "exp": norm_expires, "uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except ValueError as ve:
        logger.error("[user_db_helper] Invalid expires_at format for user_id=%s: %s", user_id, ve)
        return False
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in update_refresh_token for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in update_refresh_token for user_id=%s", user_id)
        return False


async def verify_refresh_token(user_id: str, raw_token: str) -> bool:
    """Verify an incoming raw refresh token against the stored hash for active user."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("""
                        SELECT refresh_token, refresh_token_expires_at
                        FROM users
                        WHERE user_id = :uid AND is_active = TRUE
                    """),
                    {"uid": user_id},
                )
            ).mappings().first()

            if not row or not row.get("refresh_token"):
                return False

            expires_at = row.get("refresh_token_expires_at")
            if expires_at:
                now = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    logger.info("[user_db_helper] Refresh token expired for user_id=%s", user_id)
                    return False

            expected_hash = hash_refresh_token(raw_token)
            return hmac.compare_digest(row["refresh_token"], expected_hash)
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in verify_refresh_token for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in verify_refresh_token for user_id=%s", user_id)
        return False


async def clear_refresh_token(user_id: str) -> bool:
    """Clear a user's stored refresh token and expiry (e.g. on logout)."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET refresh_token = NULL,
                        refresh_token_expires_at = NULL,
                        updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in clear_refresh_token for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in clear_refresh_token for user_id=%s", user_id)
        return False


# ───────────────────────────────────────────────────────────────
#  USER operations — deactivate / reactivate / delete
# ───────────────────────────────────────────────────────────────

async def deactivate_user(user_id: str) -> bool:
    """Soft-delete a user by setting is_active = FALSE."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE user_id = :uid AND is_active = TRUE
                """),
                {"uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in deactivate_user for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in deactivate_user for user_id=%s", user_id)
        return False


async def reactivate_user(user_id: str) -> bool:
    """Reactivate a previously soft-deleted user."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE users
                    SET is_active = TRUE, updated_at = NOW()
                    WHERE user_id = :uid AND is_active = FALSE
                """),
                {"uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in reactivate_user for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in reactivate_user for user_id=%s", user_id)
        return False


async def delete_user(user_id: str) -> bool:
    """
    Permanently delete a user record.
    NOTE: user_mappings.user_id has a FK to users.user_id with no ON DELETE
    behavior specified in the schema, so this will fail if mappings still
    reference this user — call delete_all_user_mappings(user_id) first if
    a hard delete is truly intended. Prefer deactivate_user() in most cases.
    """
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("DELETE FROM users WHERE user_id = :uid"),
                {"uid": user_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[user_db_helper] Database error in delete_user for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in delete_user for user_id=%s", user_id)
        return False


# ───────────────────────────────────────────────────────────────
#  USER MAPPING operations — create
# ───────────────────────────────────────────────────────────────

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
        logger.exception("[user_db_helper] Database error in link_user_to_content user_id=%s, content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in link_user_to_content user_id=%s, content_id=%s", user_id, content_id)
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
        logger.exception("[user_db_helper] Database error in link_user_to_feed user_id=%s, feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in link_user_to_feed user_id=%s, feed_id=%s", user_id, feed_id)
        return False


# ───────────────────────────────────────────────────────────────
#  USER MAPPING operations — read
# ───────────────────────────────────────────────────────────────

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
        logger.exception("[user_db_helper] Database error in get_user_mappings for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_mappings for user_id=%s", user_id)
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
        logger.exception("[user_db_helper] Database error in get_user_content_ids for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_content_ids for user_id=%s", user_id)
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
        logger.exception("[user_db_helper] Database error in get_user_feed_ids for user_id=%s", user_id)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_user_feed_ids for user_id=%s", user_id)
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
        logger.exception("[user_db_helper] Database error in get_users_for_content for content_id=%s", content_id)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_users_for_content for content_id=%s", content_id)
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
        logger.exception("[user_db_helper] Database error in get_users_for_feed for feed_id=%s", feed_id)
        return []
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in get_users_for_feed for feed_id=%s", feed_id)
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
        logger.exception("[user_db_helper] Database error in user_has_content_mapping user_id=%s, content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in user_has_content_mapping user_id=%s, content_id=%s", user_id, content_id)
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
        logger.exception("[user_db_helper] Database error in user_has_feed_mapping user_id=%s, feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in user_has_feed_mapping user_id=%s, feed_id=%s", user_id, feed_id)
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
        logger.exception("[user_db_helper] Database error in count_user_mappings for user_id=%s", user_id)
        return 0
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in count_user_mappings for user_id=%s", user_id)
        return 0


# ───────────────────────────────────────────────────────────────
#  USER MAPPING operations — delete
# ───────────────────────────────────────────────────────────────

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
        logger.exception("[user_db_helper] Database error in unlink_user_from_content user_id=%s, content_id=%s", user_id, content_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in unlink_user_from_content user_id=%s, content_id=%s", user_id, content_id)
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
        logger.exception("[user_db_helper] Database error in unlink_user_from_feed user_id=%s, feed_id=%s", user_id, feed_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in unlink_user_from_feed user_id=%s, feed_id=%s", user_id, feed_id)
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
        logger.exception("[user_db_helper] Database error in delete_all_user_mappings for user_id=%s", user_id)
        return False
    except Exception:
        logger.exception("[user_db_helper] Unexpected error in delete_all_user_mappings for user_id=%s", user_id)
        return False