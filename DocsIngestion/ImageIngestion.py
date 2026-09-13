import asyncio
from io import BytesIO
import pickle
import shutil

from pathlib import Path as SyncPath
from PIL import Image
from rank_bm25 import BM25Okapi
import re
import numpy as np

import uuid
from Embeddings.Embeddingmaker import Embedder
from Dbhelper.pdf_db_helper import save_content_to_database
from langchain_community.vectorstores import FAISS

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
from Splitter.PdfSplitter import pdf_splitter
from Embeddings.Embeddingmaker import embedder as embedding_maker

_ocr_engine = None

def tokenize(text: str):
    return re.findall(r"\b\w+\b", text.lower())

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            import torch
            device = "gpu" if torch.cuda.is_available() else "cpu"
            _ocr_engine = PaddleOCR(
                lang="en",
                use_doc_orientation_classify=False,
                use_doc_unwarping=True,
                use_textline_orientation=False,
                device=device
            )
        except Exception:
            _ocr_engine = False
    return _ocr_engine


def ocr_doing(image_bytes: bytes):
    engine = get_ocr_engine()
    if not engine:
        import pytesseract
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        return pytesseract.image_to_string(image)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image_np = np.array(image)
    result = engine.predict(image_np)
    texts = []
    for res in result:
        data = res.json["res"]
        texts.extend(data["rec_texts"])
    return "\n".join(texts)


async def read_text_from_image(file):
    image_bytes = await file.read()
    result = await asyncio.to_thread(ocr_doing, image_bytes)  # fixed: pass raw bytes, not a BytesIO
    return result


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


async def ingestimage(file, name: str):
    try:
        text = await read_text_from_image(file)
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)

        chunks = await asyncio.to_thread(pdf_splitter.split, text)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)

        database_saved = await save_content_to_database(name=name, content_id=id, doc_type="image", chunks=len(chunks))
        if database_saved:
            print(f"Image ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Proccessing the Image {name} and Error is {e}")
        return None