import os
from typing import Optional
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET", "dev_secret_key_change_in_production")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "gateway_internal_secret")

PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/mock",
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
        return payload.get("username") or payload.get("sub")
    except Exception as e:
        print(f"Token verification failed: {e}")
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
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Missing Bearer Token"}
            )
        token = auth_header.split(" ", 1)[1].strip()

    username = await verify_token(token)
    if not username:
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden: Invalid or expired token"}
        )

    # Attach verified user identity to request state for downstream handlers
    request.state.user = username
    return await call_next(request)