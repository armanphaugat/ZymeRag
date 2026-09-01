import asyncio
import re
import sys
import os
from io import BytesIO
from typing import List, Optional
lock = asyncio.Lock()
URL_PATTERN = r"(https?://[^\s]+)"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp",
    ".mp4", ".mp3", ".wav", ".m4a",
    ".xlsx", ".xls",
}
from fastapi import File, Form, HTTPException, Query, UploadFile, Depends
from DocsIngestion.PdfIngestion import ingestpdf
idempotent_keys={}
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

async def upload_pdf(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        idempotent_keys[idempotent_key]=1
        upload_id_pdf=await ingestpdf(file,name)
        if upload_id_pdf is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload PDF")
        return {"message": "PDF uploaded successfully", "id": upload_id_pdf}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))