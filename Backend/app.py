import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from Backend.Middleware.auth import auth_middleware
from Backend.Router.upload_router import upload_router
from Backend.Router.delete_router import delete_router
from Backend.Router.rules_router import rules_router
from Backend.Router.gateway_router import gateway_router

app = FastAPI(
    title="Axiom Gateway API",
    description="Enterprise Policy Ingestion, Rule Review, and Zero-LLM Runtime Enforcement Gateway",
    version="2.0.0",
)

# 1. Attach Global Authentication Middleware
app.middleware("http")(auth_middleware)

# 2. Health & Status Probe
@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "service": "Axiom Gateway",
        "version": "2.0.0",
    }

# 3. Register Core Routers
app.include_router(upload_router, prefix="/upload", tags=["Policy Ingestion"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])
app.include_router(rules_router, prefix="/rules", tags=["Policy Rules"])
app.include_router(gateway_router, prefix="/actions", tags=["Runtime Enforcement"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("Backend.app:app", host="0.0.0.0", port=8000, reload=True)
