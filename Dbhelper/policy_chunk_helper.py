import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from Dbhelper.db import AsyncDB


async def save_policy_chunks(doc_id: str, chunks: List[Any], faiss_path: str) -> List[Dict[str, Any]]:
    """
    Saves parsed document chunks into the policy_chunks table.
    Captures section headings from LangChain Document metadata if present.
    Returns the list of created chunk dictionaries with generated chunk_ids.
    """
    records = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        content = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        metadata = chunk.metadata if hasattr(chunk, "metadata") and chunk.metadata else {}
        
        # Build heading hierarchy from MarkdownHeaderTextSplitter metadata (h1, h2, h3, h4)
        headings = [metadata[k] for k in ("h1", "h2", "h3", "h4") if k in metadata and metadata[k]]
        section_heading = " > ".join(headings) if headings else metadata.get("section") or None
        page_number = metadata.get("page") or metadata.get("page_number") or 1

        records.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "section_heading": section_heading,
            "page_number": int(page_number) if str(page_number).isdigit() else 1,
            "text": content,
            "faiss_path": faiss_path,
        })

    if not records:
        return []

    try:
        async with AsyncDB() as session:
            for rec in records:
                await session.execute(
                    text("""
                        INSERT INTO policy_chunks
                            (chunk_id, doc_id, section_heading, page_number, text, faiss_path)
                        VALUES
                            (:chunk_id, :doc_id, :section_heading, :page_number, :text, :faiss_path)
                    """),
                    rec,
                )
            await session.commit()
            return records
    except Exception as e:
        print(f"Error saving policy chunks for doc {doc_id}: {e}")
        return []


async def get_policy_chunks_by_doc_id(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieves all policy chunks associated with a document."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT chunk_id, doc_id, section_heading, page_number, text, faiss_path, created_at
                    FROM policy_chunks
                    WHERE doc_id = :doc_id
                    ORDER BY page_number ASC, created_at ASC
                """),
                {"doc_id": doc_id},
            )
            return [dict(row) for row in result.mappings().fetchall()]
    except Exception as e:
        print(f"Error retrieving chunks for doc {doc_id}: {e}")
        return []


async def get_policy_chunk_by_id(chunk_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single policy chunk by its chunk_id."""
    try:
        async with AsyncDB() as session:
            result = await session.execute(
                text("""
                    SELECT chunk_id, doc_id, section_heading, page_number, text, faiss_path, created_at
                    FROM policy_chunks
                    WHERE chunk_id = :chunk_id
                """),
                {"chunk_id": chunk_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception as e:
        print(f"Error retrieving policy chunk {chunk_id}: {e}")
        return None
