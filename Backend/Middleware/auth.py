import os
from typing import Optional
from dotenv import load_dotenv
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

load_dotenv()

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


async def verify_token(token: str) -> Optional[str]:
    """Verifies a JWT Bearer token or static API key."""
    if not token:
        return None
    # Support direct API key for agent service-to-service calls
    if token == GATEWAY_API_KEY:
        return "service_agent"
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            print("[Auth Warning] Token with wrong type presented as access token")
            return None
        return payload.get("user_id") or payload.get("username") or payload.get("sub")
    except jwt.ExpiredSignatureError:
        print("[Auth Info] Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[Auth Info] Invalid access token: {e}")
        return None


async def auth_middleware(request: Request, call_next):
    """
    Global authentication middleware.
    Checks JWT access token from cookies or Authorization Bearer header.
    Bypasses documentation and public health routes.
    """
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

    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(status_code=403, content={"detail": "Forbidden: Invalid or expired token"})

    request.state.user = user_id
    request.state.user_id = user_id
    return await call_next(request)
