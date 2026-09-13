import os

import jwt
from fastapi import Request, HTTPException

ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
if not ACCESS_TOKEN_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET environment variable is not set")


async def verify_token(token: str):
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            print("Token with wrong type presented as access token")
            return None
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        print("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        print("Invalid access token:", e)
        return None


async def auth_middleware(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = auth_header.split(" ", 1)[1]

    user_id = await verify_token(token)
    if not user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    request.state.user_id = user_id
    return user_id