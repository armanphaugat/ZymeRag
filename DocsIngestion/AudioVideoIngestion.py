import asyncio
import os
import tempfile
import uuid
from pathlib import Path as SyncPath

import ffmpeg
from faster_whisper import WhisperModel

from Dbhelper.pdf_db_helper import save_content_to_database
from Splitter.PdfSplitter import PdfTextSplitter
from Embeddings.Embeddingmaker import Embedder
from langchain_community.vectorstores import FAISS

BASE_DIR = SyncPath("Data").resolve()
content_dir = BASE_DIR / "Content"
pdf_splitter = PdfTextSplitter()
embedding_maker = Embedder()

whisper_model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16",   
)


def transcribe_audio_file(audio_path: str) -> str:
    segments, _info = whisper_model.transcribe(audio_path, beam_size=5)
    texts = [segment.text.strip() for segment in segments]
    return "\n".join(t for t in texts if t)


def extract_audio_from_video(video_path: str, audio_out_path: str) -> None:
    (
        ffmpeg
        .input(video_path)
        .output(audio_out_path, ac=1, ar=16000, format="wav")
        .overwrite_output()
        .run(quiet=True)
    )


def _build_and_save_index_sync(chunks, content_path: SyncPath):
    vectorstore = FAISS.from_documents(chunks, embedding_maker)
    vectorstore.save_local(str(content_path))


async def read_text_from_audio(file) -> str:
    audio_bytes = await file.read()
    suffix = SyncPath(getattr(file, "filename", "audio.wav")).suffix or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        text = await asyncio.to_thread(transcribe_audio_file, tmp_path)
    finally:
        os.remove(tmp_path)

    return text


async def ingestaudio(file, name: str):
    try:
        text = await read_text_from_audio(file)
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)

        chunks = await asyncio.to_thread(pdf_splitter.split, text)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)

        database_saved = await save_content_to_database(name=name, content_id=id, doc_type="audio", chunks=len(chunks))
        if database_saved:
            print(f"Audio ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Proccessing the Audio {name} and Error is {e}")
        return None


async def read_text_from_video(file) -> str:
    video_bytes = await file.read()
    v_suffix = SyncPath(getattr(file, "filename", "video.mp4")).suffix or ".mp4"

    with tempfile.NamedTemporaryFile(suffix=v_suffix, delete=False) as tmp_video:
        tmp_video.write(video_bytes)
        tmp_video_path = tmp_video.name

    tmp_audio_path = tmp_video_path + ".wav"

    try:
        await asyncio.to_thread(extract_audio_from_video, tmp_video_path, tmp_audio_path)
        text = await asyncio.to_thread(transcribe_audio_file, tmp_audio_path)
    finally:
        for p in (tmp_video_path, tmp_audio_path):
            if os.path.exists(p):
                os.remove(p)

    return text


async def ingestvideo(file, name: str):
    try:
        text = await read_text_from_video(file)
        id = str(uuid.uuid4())
        content_path = content_dir / f"{id}"
        await asyncio.to_thread(content_path.mkdir, parents=True, exist_ok=True)

        chunks = await asyncio.to_thread(pdf_splitter.split, text)
        await asyncio.to_thread(_build_and_save_index_sync, chunks, content_path)

        database_saved = await save_content_to_database(name=name, content_id=id, doc_type="video", chunks=len(chunks))
        if database_saved:
            print(f"Video ingested and saved to database with ID: {id}")
            return id
        return None
    except Exception as e:
        print(f"Error Occured While Proccessing the Video {name} and Error is {e}")
        return None
