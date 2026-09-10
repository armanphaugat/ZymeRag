import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from Backend.Middleware.auth import auth_middleware
from Backend.Router.upload_router import upload_router
from Backend.Router.delete_router import delete_router
from Backend.Router.rules_router import rules_router
from Backend.Router.gateway_router import gateway_router
from Backend.Router.query_router import query_router
from Backend.Router.user_router import user_router

app = FastAPI(
    title="ZymeRag & Axiom Gateway API",
    description="Enterprise Policy Ingestion, RAG Query, Rule Review, and Zero-LLM Runtime Enforcement Gateway",
    version="2.0.0",
)

# 1. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Attach Global Authentication Middleware
app.middleware("http")(auth_middleware)

# 3. Health & Status Probe
@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "service": "ZymeRag Axiom Gateway",
        "version": "2.0.0",
    }

# 4. Register Core Routers
app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])
app.include_router(rules_router, prefix="/rules", tags=["Policy Rules"])
app.include_router(gateway_router, prefix="/actions", tags=["Runtime Enforcement"])
app.include_router(query_router, prefix="/query", tags=["Query"])
app.include_router(user_router, prefix="/user", tags=["User"])

# 5. Static UI Hosting
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("Backend.app:app", host="0.0.0.0", port=8000, reload=True)
