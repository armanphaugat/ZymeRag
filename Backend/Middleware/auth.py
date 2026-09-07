import os

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse



ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
if not ACCESS_TOKEN_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET environment variable is not set")

app = FastAPI()

async def verify_token(token: str):
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            print.warning("Token with wrong type presented as access token")
            return None
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        print.info("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        print.info("Invalid access token: %s", e)
        return None

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        token = auth_header.split(" ", 1)[1]

    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    request.state.user_id = user_id
    return await call_next(request)