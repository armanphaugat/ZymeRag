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

ocr=PaddleOCR(
    lan="en",
    use_doc_orientation_classify=False,
    use_doc_unwraping=True,
    use_textline_orientation=False,
    device="gpu"
)

async def read_text_from_image(file):
    image_bytes = await file.read()
    stream=BytesIO(image_bytes)
    result=ocr.predict(stream)
    text=[]
    for res in result:
        data=res.join["res"]
        text.extend(data["rec_texts"])
    return "\n".join(text)

async def ingestimage(file,name:str):
    try:
        text=await read_text_from_image(file)
        id=str(uuid.uuid4())
        content_path=content_dir/f"{id}"
        await content_path.mkdir(parents=True,exist_ok=True)
        vectorstore=FAISS.from_documents(text,embedding_maker)
        vectorstore.save_local(str(content_path))
        database_saved=await save_content_to_database(name,id)
        if database_saved:
            print(f"Image ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Proccessing the Image {name} and Error is {e}")
        return None