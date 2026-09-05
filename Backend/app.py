import os
from fastapi import FastAPI, UploadFile, File

from Backend.Router.upload_router import upload_router
from Backend.Router.delete_router import delete_router

app=FastAPI(title="ZymeRag Backend API", description="API for ZymeRag Backend", version="1.0.0")
app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])