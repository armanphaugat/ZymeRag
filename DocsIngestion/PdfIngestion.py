import asyncio
from io import BytesIO
import os
import shutil
import re
from pathlib import Path as SyncPath
import anyio
import uuid
import pickle

import torch._dynamo
torch._dynamo.config.suppress_errors = True

try:
    import pymupdf
except ImportError:
    pymupdf = None

from Splitter.PdfSplitter import PdfTextSplitter
from Embeddings.Embeddingmaker import Embedder
from rank_bm25 import BM25Okapi
from langchain_community.vectorstores import FAISS

try:
    from docling.document_converter import DocumentConverter, DocumentStream
    converter = DocumentConverter()
except Exception:
    converter = None

from Dbhelper.pdf_db_helper import save_content_to_database
from Dbhelper.policy_chunk_helper import save_policy_chunks

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()


def _convert_pdf_sync(stream: BytesIO, filename: str):
    if converter is not None:
        try:
            source = DocumentStream(name=filename, stream=stream)
            result = converter.convert(source)
            return result.document.export_to_markdown()
        except Exception as e:
            print(f"[Docling Warning] Conversion failed, falling back to PyMuPDF: {e}")

    if pymupdf is not None:
        doc = pymupdf.open(stream=stream.getvalue(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        return text

    raise RuntimeError("Neither Docling nor PyMuPDF is available for PDF conversion")


async def read_text_from_pdf(file):
    print(f"Reading PDF file: {file.filename}")
    pdf_bytes = await file.read()
    stream = BytesIO(pdf_bytes)
    markdown = await asyncio.to_thread(_convert_pdf_sync, stream, file.filename)
    return markdown


def tokenize(text: str):
    return re.findall(r"\b\w+\b", text.lower())


def _build_and_save_index_sync(chunks, content_path: SyncPath):
    vectorstore = FAISS.from_documents(chunks, embedding_maker)
    vectorstore.save_local(str(content_path))

    documents = [chunk.page_content for chunk in chunks]
    tokenized_documents = [tokenize(document) for document in documents]
    bm25 = BM25Okapi(tokenized_documents)
    bm25_data = {"documents": documents, "bm25": bm25}
    bm25_path = content_path / "bm25.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25_data, f)


async def ingest_pdf(file, name: str):
    """
    Ingests a policy document (PDF or DOCX):
    1. Converts document to Markdown via Docling.
    2. Chunks content via section/header-aware PdfTextSplitter.
    3. Builds and persists local FAISS index & BM25 index.
    4. Records document entry in contents table.
    5. Records chunk metadata in policy_chunks table for SQL traceability.
    6. Triggers offline rule extraction (Groq LLM) to generate DRAFT rules in rules table.
    """
    try:
        print(f"Reading PDF: {file.filename}")
        markdown = await read_text_from_pdf(file)
        chunks = await asyncio.to_thread(pdf_splitter.split, markdown)
        doc_id = str(uuid.uuid4())
        content_path = content_dir / f"{doc_id}"
        print(f"Creating content directory for PDF: {file.filename}")
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)
        print(f"PDF ingested and index built for: {file.filename}")
        database_saved = await save_content_to_database(name=name, content_id=doc_id, doc_type="pdf", chunks=len(chunks))
        print(f"Database save status for PDF: {file.filename} - {database_saved}")
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
