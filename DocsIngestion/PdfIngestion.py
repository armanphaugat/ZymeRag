import asyncio
from io import BytesIO
import shutil

from pathlib import Path as SyncPath
import anyio
from Dbhelper.website_db_helper import save_pdf_to_database
from Splitter.PdfSplitter import PdfTextSplitter
import uuid
from Embeddings.Embeddingmaker import Embedder
from langchain_community.vectorstores import FAISS
from docling.document_converter import DocumentConverter
from Dbhelper.pdf_db_helper import save_content_to_database

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
converter = DocumentConverter()
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()


def _convert_pdf_sync(stream: BytesIO):
    result = converter.convert(stream)
    documents = result.document
    return documents.export_to_markdown()


async def read_text_from_pdf(file):
    pdf_bytes = await file.read()
    stream = BytesIO(pdf_bytes)
    markdown = await asyncio.to_thread(_convert_pdf_sync, stream)
    return markdown


def _build_and_save_index_sync(chunks, content_path: SyncPath):
    vectorstore = FAISS.from_documents(chunks, embedding_maker)
    vectorstore.save_local(str(content_path))


async def ingest_pdf(file, name: str):
    try:
        markdown = await read_text_from_pdf(file)
        chunks = await asyncio.to_thread(pdf_splitter.split, markdown)
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)
        database_saved = await save_content_to_database(name, id)
        if database_saved:
            print(f"Pdf ingested and saved to database with ID: {id}")
            return id
        return None

    except Exception as e:
        print(f"Error occurred while reading PDF: {e}")
        return None


async def delete_content(id: str):
    try:
        content_path = content_dir / f"{id}"
        exists = await asyncio.to_thread(content_path.exists)
        if exists:
            await asyncio.to_thread(shutil.rmtree, content_path)
            print(f"Pdf with ID: {id} deleted successfully.")
            return True
        else:
            print(f"Pdf with ID: {id} does not exist.")
            return False
    except Exception as e:
        print(f"Error occurred while deleting PDF: {e}")
        return False