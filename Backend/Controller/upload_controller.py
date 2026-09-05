import asyncio
import re
import sys
import os
from io import BytesIO
from typing import List, Optional

from DocsIngestion.AudioVideoIngestion import ingestaudio, ingestvideo
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
from DocsIngestion.PdfIngestion import ingest_pdf
from DocsIngestion.ImageIngestion import ingestimage
from DocsIngestion.CsvIngestion import ingestCsv
idempotent_keys={}
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

async def upload_pdf(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["application/pdf"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
        idempotent_keys[idempotent_key]=1
        upload_id_pdf=await ingest_pdf(file, name)
        if upload_id_pdf is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload PDF")
        return {"message": "PDF uploaded successfully", "id": upload_id_pdf}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def upload_docx(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only DOCX files are allowed.")
        idempotent_keys[idempotent_key]=1
        file_size_bytes=file.size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 10:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="File size exceeds the maximum limit of 10MB")
        upload_id_docx=await ingest_pdf(file, name)
        if upload_id_docx is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload docx")
        return {"message": "docx uploaded successfully", "id": upload_id_docx}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def upload_image(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["image/jpeg","image/png"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG and PNG images are allowed.")
        idempotent_keys[idempotent_key]=1
        file_size_bytes=file.size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 10:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="File size exceeds the maximum limit of 10MB")
        upload_id_image=await ingestimage(file,name)
        if upload_id_image is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload image")
        return {"message": "image uploaded successfully", "id": upload_id_image}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def upload_csv(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["text/csv"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only CSV files are allowed.")
        idempotent_keys[idempotent_key]=1
        file_size_bytes=file.size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 10:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="File size exceeds the maximum limit of 10MB")
        upload_id_csv=await ingestCsv(file,name)
        if upload_id_csv is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload csv")
        return {"message": "csv uploaded successfully", "id": upload_id_csv}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

async def upload_audio(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["audio/mpeg","audio/wav","audio/x-wav","audio/x-m4a"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only MP3, WAV, and M4A audio files are allowed.")
        idempotent_keys[idempotent_key]=1
        file_size_bytes=file.size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 10:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="File size exceeds the maximum limit of 10MB")
        upload_id_audio=await ingestaudio(file,name)
        if upload_id_audio is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload audio")
        return {"message": "audio uploaded successfully", "id": upload_id_audio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def upload_video(file: UploadFile = File(...), name: str = Form(...), idempotent_key: Optional[str] = Form(None)):
    try:
        async with lock:
            if idempotent_key:
                if idempotent_key in idempotent_keys:
                    return {"message": "Duplicate request", "id": idempotent_keys[idempotent_key]}
        if file.content_type not in ["video/mp4","video/x-m4v","video/quicktime"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only MP4, M4V, and MOV video files are allowed.")
        idempotent_keys[idempotent_key]=1
        file_size_bytes=file.size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > 10:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="File size exceeds the maximum limit of 10MB")
        upload_id_video=await ingestvideo(file,name)
        if upload_id_video is None:
            idempotent_keys.pop(idempotent_key, None)
            raise HTTPException(status_code=400, detail="Failed to upload video")
        return {"message": "video uploaded successfully", "id": upload_id_video}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))