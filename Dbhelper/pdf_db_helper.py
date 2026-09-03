import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from Dbhelper.db import AsyncDB

logger = logging.getLogger(__name__)


async def save_content_to_database(
    name: str,
    content_id: str,
    doc_type: str = "pdf",
    chunks: int = 0,
    file_size: Optional[int] = None,
) -> bool:
    """Insert a new document content record into contents table."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    INSERT INTO contents (content_id, name, file_type, file_size, chunks)
                    VALUES (:cid, :name, :ftype, :fsize, :chunks)
                    ON CONFLICT (content_id) DO NOTHING
                """),
                {
                    "cid": content_id,
                    "name": name,
                    "ftype": doc_type,
                    "fsize": file_size,
                    "chunks": chunks,
                },
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[pdf_db_helper] Database error saving content %s (content_id: %s)", name, content_id)
        return False
    except Exception:
        logger.exception("[pdf_db_helper] Unexpected error saving content %s (content_id: %s)", name, content_id)
        return False


async def update_content_chunks(content_id: str, chunks: int) -> bool:
    """Update the chunk count for a document content record."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("""
                    UPDATE contents
                    SET chunks = :chunks
                    WHERE content_id = :cid AND deleted_at IS NULL
                """),
                {"chunks": chunks, "cid": content_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[pdf_db_helper] Database error updating chunks for content_id=%s", content_id)
        return False
    except Exception:
        logger.exception("[pdf_db_helper] Unexpected error updating chunks for content_id=%s", content_id)
        return False


async def get_document_by_id(content_id: str) -> Optional[dict]:
    """Fetch a single active content record by content_id."""
    try:
        async with AsyncDB() as s:
            row = (
                await s.execute(
                    text("SELECT * FROM contents WHERE content_id = :cid AND deleted_at IS NULL"),
                    {"cid": content_id},
                )
            ).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError:
        logger.exception("[pdf_db_helper] Database error retrieving document with content_id %s", content_id)
        return None
    except Exception:
        logger.exception("[pdf_db_helper] Unexpected error retrieving document with content_id %s", content_id)
        return None


async def delete_content_from_database(content_id: str) -> bool:
    """Soft-delete a content record by setting deleted_at."""
    try:
        async with AsyncDB() as s:
            result = await s.execute(
                text("UPDATE contents SET deleted_at = NOW() WHERE content_id = :cid AND deleted_at IS NULL"),
                {"cid": content_id},
            )
            await s.commit()
            return (result.rowcount or 0) > 0
    except SQLAlchemyError:
        logger.exception("[pdf_db_helper] Database error soft deleting document with content_id %s", content_id)
        return False
    except Exception:
        logger.exception("[pdf_db_helper] Unexpected error soft deleting document with content_id %s", content_id)
        return False