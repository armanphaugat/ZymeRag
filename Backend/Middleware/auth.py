import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

load_dotenv()
logger = logging.getLogger(__name__)

ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET", "dev_secret_key_change_in_production")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "gateway_internal_secret")

PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/ui",
}

PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/mock",
    "/static",
    "/user",
)


async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Fast in-memory verification of JWT Bearer token or static API key.
    """
    if not token:
        return None
    if token == GATEWAY_API_KEY:
        return {"user_id": "service_agent", "username": "service_agent", "role": "admin"}
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        user_id = payload.get("user_id") or payload.get("username") or payload.get("sub")
        if not user_id:
            return None
        username = payload.get("username") or str(user_id)
        role = payload.get("role") or "compliance_officer"
        return {"user_id": str(user_id), "username": str(username), "role": str(role).lower()}
    except Exception as e:
        logger.info(f"[Auth] Token decode error: {e}")
        return None


async def auth_middleware(request: Request, call_next):
    """
    Global authentication and role-based context middleware.
    Checks JWT access token from cookies or Authorization Bearer header.
    Bypasses documentation, CORS preflights, and public health routes.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # Bypass public routes
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return await call_next(request)

    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: Missing Bearer Token"})
        token = auth_header.split(" ", 1)[1].strip()

    token_data = await verify_token(token)
    if not token_data:
        return JSONResponse(status_code=403, content={"detail": "Forbidden: Invalid or expired token"})

    user_id = token_data["user_id"]
    username = token_data.get("username", user_id)
    role = token_data.get("role", "compliance_officer")

    request.state.user = username
    request.state.username = username
    request.state.user_id = user_id
    request.state.role = role
    return await call_next(request)
