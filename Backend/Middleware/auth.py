from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import jwt
import os
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
app=FastAPI()

async def verify_token(token: str):
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        return payload.get("username")
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = request.cookies.get("access_token")
    if not token:
        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"}
            )
        token = token.split(" ", 1)[1]
    username=await verify_token(token)
    if not username:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    response = await call_next(request)
    return response