import asyncio
from io import BytesIO
import re
import shutil
import pickle
from pathlib import Path as SyncPath
import anyio


import uuid
from Embeddings.Embeddingmaker import Embedder
from Dbhelper.pdf_db_helper import save_content_to_database
BASE_DIR=SyncPath("Data").resolve()
content_dir=BASE_DIR/"Content"
from Splitter.PdfSplitter import pdf_splitter
from rank_bm25 import BM25Okapi
from Embeddings.Embeddingmaker import embedder as embedding_maker
from langchain_community.vectorstores import FAISS

from langchain_core.documents import Document
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
