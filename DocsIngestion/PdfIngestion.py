import asyncio
from io import BytesIO
import shutil
import re
import fitz
import torch._dynamo
torch._dynamo.config.suppress_errors = True
import pymupdf
from pathlib import Path as SyncPath
import anyio
from Splitter.PdfSplitter import PdfTextSplitter
import uuid
import pickle
from Embeddings.Embeddingmaker import Embedder
from rank_bm25 import BM25Okapi
from langchain_community.vectorstores import FAISS
import torch._dynamo
torch._dynamo.config.suppress_errors = True
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("CUDA:", torch.version.cuda)
try:
    from docling.document_converter import DocumentConverter, DocumentStream
    converter = DocumentConverter()
except ImportError:
    converter = None

from Dbhelper.pdf_db_helper import save_content_to_database

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()


def _convert_pdf_sync(stream: BytesIO, filename: str):
    if converter is not None:
        source = DocumentStream(
            name=filename,
            stream=stream
        )

        result = converter.convert(source)

        return result.document.export_to_markdown()
    doc = pymupdf.open(
        stream=stream.getvalue(),
        filetype="pdf"
    )
    text = "\n".join(
        page.get_text()
        for page in doc
    )
    return text

def _convert_pdf_sync_fitz(file_bytes:bytes):
    doc=fitz.open(stream=file_bytes, filetype="pdf")
    pages_text=[]
    for page in doc:
        text = page.get_text("text")
        pages_text.append(text)
    doc.close()
    return "\n".join(pages_text)

async def read_text_from_pdf(file):
    print(f"Reading PDF file: {file.filename}")
    pdf_bytes = await file.read()
    stream = BytesIO(pdf_bytes)
    markdown = await asyncio.to_thread(_convert_pdf_sync, stream,file.filename)
    if markdown is None:
        print(f"Converter failed for {file.filename}, falling back to PyMuPDF")
        markdown = await asyncio.to_thread(_convert_pdf_sync_fitz, pdf_bytes)
    return markdown

def tokenize(text: str):
    return re.findall(r"\b\w+\b", text.lower())

def _build_and_save_index_sync(chunks, content_path: SyncPath):
    vectorstore = FAISS.from_documents(
        chunks,
        embedding_maker
    )
    vectorstore.save_local(
        str(content_path)
    )
    documents = [
        chunk.page_content
        for chunk in chunks
    ]
    tokenized_documents = [
        tokenize(document)
        for document in documents
    ]
    bm25 = BM25Okapi(
        tokenized_documents
    )
    bm25_data = {
        "documents": documents,
        "bm25": bm25
    }
    bm25_path = content_path / "bm25.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump(
            bm25_data,
            f
        )


async def ingest_pdf(file, name: str):
    try:
        print(f"Reading PDF: {file.filename}")
        markdown = await read_text_from_pdf(file)
        chunks = await asyncio.to_thread(pdf_splitter.split, markdown)
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        print(f"Creating content directory for PDF: {file.filename}")
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)
        print(f"PDF ingested and index built for: {file.filename}")
        database_saved = await save_content_to_database(name=name, content_id=id, doc_type="pdf", chunks=len(chunks))
        print(f"Database save status for PDF: {file.filename} - {database_saved}")
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