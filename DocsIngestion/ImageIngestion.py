import asyncio
from io import BytesIO
import shutil

from pathlib import Path as SyncPath
from PIL import Image
import numpy as np
from Splitter.PdfSplitter import PdfTextSplitter
import uuid
from Embeddings.Embeddingmaker import Embedder
from langchain_community.vectorstores import FAISS
from docling.document_converter import DocumentConverter
from Dbhelper.pdf_db_helper import save_content_to_database
from paddleocr import PaddleOCR

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
converter = DocumentConverter()
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()

ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=True,
    use_textline_orientation=False,
    device="gpu"
)


def ocr_doing(image_bytes: bytes):
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image = np.array(image)
    result = ocr.predict(image)
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
    vectorstore = FAISS.from_documents(chunks, embedding_maker)
    vectorstore.save_local(str(content_path))


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