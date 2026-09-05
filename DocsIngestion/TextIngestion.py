import asyncio
from io import BytesIO
import shutil

from pathlib import Path as SyncPath
import anyio

from Splitter.PdfSplitter import PdfTextSplitter
import uuid
from Embeddings.Embeddingmaker import Embedder
from langchain_community.vectorstores import FAISS
from docling.document_converter import DocumentConverter
from Dbhelper.pdf_db_helper import save_content_to_database
from paddleocr import PaddleOCR
BASE_DIR=SyncPath("Data").resolve()
content_dir=BASE_DIR/"Content"
converter = DocumentConverter()
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()


from langchain_core.documents import Document

def _build_and_save_index_sync(chunks, content_path: SyncPath):
    vectorstore = FAISS.from_documents(chunks, embedding_maker)
    vectorstore.save_local(str(content_path))

async def ingestText(text: str, name: str):
    try:
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)
        if len(text) > 300:
            chunks = await asyncio.to_thread(pdf_splitter.split, text)
        else:
            chunks = [Document(page_content=text)]
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)
        database_saved = await save_content_to_database(name=name, content_id=id, doc_type="txt", chunks=len(chunks))
        if database_saved:
            print(f"Text ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Ingesting The Text {name} and Error is {e}")
        return None
