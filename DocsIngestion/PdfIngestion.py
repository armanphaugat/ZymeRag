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
from Dbhelper.pdf_db_helper import save_pdf_to_database
BASE_DIR=SyncPath("Data").resolve()
content_dir=BASE_DIR/"Content"
converter = DocumentConverter()
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()

async def read_text_from_pdf(file):
    pdf_bytes = await file.read()
    stream=BytesIO(pdf_bytes)
    result = converter.convert(stream)
    documents = result.document
    return documents.export_to_markdown()

async def ingest_pdf(file,name:str):
    try:
        markdown = await read_text_from_pdf(file)
        chunks = pdf_splitter.split(markdown)
        id=str(uuid.uuid4())
        content_path=content_dir/f"{id}"
        await content_path.mkdir(parents=True,exist_ok=True)
        vectorstore=FAISS.from_documents(chunks,embedding_maker)
        vectorstore.save_local(str(content_path))
        database_saved=await save_pdf_to_database(name,id)
        if database_saved:
            print(f"Pdf ingested and saved to database with ID: {id}")
            return id
        return None
        
    except Exception as e:
        print(f"Error occurred while reading PDF: {e}")
        return None

async def delete_pdf(id:str):
    try:
        content_path=content_dir/f"{id}"
        if await content_path.exists():
            await anyio.to_thread.run_sync(shutil.rmtree, content_path)
            print(f"Pdf with ID: {id} deleted successfully.")
            return True
        else:
            print(f"Pdf with ID: {id} does not exist.")
            return False
    except Exception as e:
        print(f"Error occurred while deleting PDF: {e}")
        return False

