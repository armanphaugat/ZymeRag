import asyncio
from io import BytesIO
import shutil
import uuid
from pathlib import Path as SyncPath

from Dbhelper.pdf_db_helper import save_content_to_database
from Dbhelper.policy_chunk_helper import save_policy_chunks
from Splitter.PdfSplitter import PdfTextSplitter

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
pdf_splitter = PdfTextSplitter()

_converter = None
_embedding_maker = None


def get_converter():
    """Lazy loader for Docling DocumentConverter to prevent slow server startup."""
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter


def get_embedder():
    """Lazy loader for SentenceTransformer embedder."""
    global _embedding_maker
    if _embedding_maker is None:
        from Embeddings.Embeddingmaker import Embedder
        _embedding_maker = Embedder()
    return _embedding_maker


def _convert_pdf_sync(stream: BytesIO):
    converter = get_converter()
    result = converter.convert(stream)
    documents = result.document
    return documents.export_to_markdown()


async def read_text_from_pdf(file):
    pdf_bytes = await file.read()
    stream = BytesIO(pdf_bytes)
    markdown = await asyncio.to_thread(_convert_pdf_sync, stream)
    return markdown


def _build_and_save_index_sync(chunks, content_path: SyncPath):
    from langchain_community.vectorstores import FAISS
    embedder = get_embedder()
    vectorstore = FAISS.from_documents(chunks, embedder)
    vectorstore.save_local(str(content_path))


async def ingest_pdf(file, name: str):
    """
    Ingests a policy document (PDF or DOCX):
    1. Converts document to Markdown via Docling.
    2. Chunks content via section/header-aware PdfTextSplitter.
    3. Builds and persists local FAISS index.
    4. Records document entry in contents table.
    5. Records chunk metadata in policy_chunks table for SQL traceability.
    6. Triggers offline rule extraction (Groq LLM) to generate DRAFT rules in rules table.
    """
    try:
        markdown = await read_text_from_pdf(file)
        chunks = await asyncio.to_thread(pdf_splitter.split, markdown)
        doc_id = str(uuid.uuid4())
        content_path = content_dir / f"{doc_id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)

        database_saved = await save_content_to_database(
            name=name,
            content_id=doc_id,
            doc_type="pdf",
            chunks=len(chunks)
        )
        if database_saved:
            print(f"[PolicyIngestion] Document '{name}' saved to database with ID: {doc_id}")

            # Save chunks to PostgreSQL policy_chunks table
            saved_chunks = await save_policy_chunks(doc_id, chunks, str(content_path))
            print(f"[PolicyIngestion] Persisted {len(saved_chunks)} chunks to policy_chunks for doc {doc_id}")

            # Trigger offline rule extraction as a background task
            try:
                from Backend.RuleExtraction.extract_rules import extract_rules_from_document
                asyncio.create_task(extract_rules_from_document(doc_id, saved_chunks))
            except Exception as ex:
                print(f"[PolicyIngestion] Warning: Could not launch background rule extraction: {ex}")

            return doc_id

        return None

    except Exception as e:
        print(f"Error occurred while ingesting policy document: {e}")
        return None


async def delete_content(id: str):
    try:
        content_path = content_dir / f"{id}"
        exists = await asyncio.to_thread(content_path.exists)
        if exists:
            await asyncio.to_thread(shutil.rmtree, content_path)
            print(f"Content directory with ID: {id} deleted successfully.")
            return True
        else:
            print(f"Content with ID: {id} does not exist.")
            return False
    except Exception as e:
        print(f"Error occurred while deleting content: {e}")
        return False
