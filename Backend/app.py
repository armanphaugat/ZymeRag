import os
from fastapi import FastAPI, UploadFile, File

from Backend.Router import upload_router,delete_router

app=FastAPI(title="ZymeRag Backend API", description="API for ZymeRag Backend", version="1.0.0")
app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])