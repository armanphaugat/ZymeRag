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
from paddleocr import PaddleOCR
BASE_DIR=SyncPath("Data").resolve()
content_dir=BASE_DIR/"Content"
converter = DocumentConverter()
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()




async def ingestText(text:str,name:str):
    try:
        id=str(uuid.uuid4())
        content_path=content_dir/f"{id}"
        content_path.mkdir(parents=True,exist_ok=True)
        if len(text)>300:
            chunks=pdf_splitter.split(text)
            vectorstore=FAISS.from_documents(chunks,embedding_maker)
            vectorstore.save_local(str(content_path))
        else:
            vectorstore=FAISS.from_documents(text,embedding_maker)
            vectorstore.save_local(str(content_path))
        database_saved=await save_content_to_database(name,id)
        if database_saved:
            print(f"Text ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Ingesting The Image {name} and Error is {e}")
        return None
