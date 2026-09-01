import os
from fastapi import FastAPI, UploadFile, File

from Backend.Router import upload_router

app=FastAPI(title="ZymeRag Backend API", description="API for ZymeRag Backend", version="1.0.0")
app.include_router(upload_router, prefix="/upload", tags=["Upload"])