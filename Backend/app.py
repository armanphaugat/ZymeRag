import os
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from Backend.Router.upload_router import upload_router
from Backend.Router.delete_router import delete_router
from Backend.Router.user_router import user_router
from Backend.Router.query_router import query_router
app = FastAPI(title="ZymeRag Backend API", description="API for ZymeRag Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])
app.include_router(query_router, prefix="/query", tags=["Query"])
app.include_router(user_router, prefix="/user", tags=["User"])

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
@app.get("/ui")
async def read_ui():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ZymeRag API is running. Testing UI index.html not found."}