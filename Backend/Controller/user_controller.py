import os
import uuid
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Response, Request
from pydantic import BaseModel

from Dbhelper.user_db_helper import (
    clear_refresh_token,
    create_user as db_create_user,
    get_user_by_email,
    get_user_by_username,
    update_refresh_token,
    verify_refresh_token,
)
from Backend.Utils.Hash import hash_password

logger = logging.getLogger(__name__)

ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "15"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))

if not ACCESS_TOKEN_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET environment variable is not set")


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    user_id: Optional[str] = None
    refresh_token: Optional[str] = None


class LogoutRequest(BaseModel):
    user_id: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str



def create_jwt(user_id: str, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")


async def create_access_token(user_id: str) -> str:
    try:
        return create_jwt(user_id, "access", timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES))
    except Exception as e:
        logger.exception("Failed to create access token for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Could not create access token") from e


async def create_refresh_token(user_id: str) -> str:
    try:
        return secrets.token_urlsafe(48)
    except Exception as e:
        logger.exception("Failed to create refresh token for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Could not create refresh token") from e


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


async def create_user(
    response: Response,
    payload: CreateUserRequest,
):
    try:
        username = payload.username
        password = payload.password
        email = payload.email or f"{username}@example.com"

        existing_user = await get_user_by_username(username)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this username already exists")

        user_id = str(uuid.uuid4())
        hashed_password = await hash_password(password)
        created = await db_create_user(user_id=user_id, username=username, email=email, password_hash=hashed_password)
        if not created:
            raise HTTPException(status_code=500, detail="Could not create user in database")

        access_token = await create_access_token(user_id=user_id)
        refresh_token = await create_refresh_token(user_id=user_id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        stored_ok = await update_refresh_token(
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            hash_token=True,
        )
        if not stored_ok:
            raise HTTPException(status_code=500, detail="Could not persist refresh token")
        _set_refresh_cookie(response, refresh_token)

        return {
            "message": "User created successfully",
            "user_id": user_id,
            "username": username,
            "email": email,
            "access_token": access_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_user for username=%s", payload.username)
        raise HTTPException(status_code=500, detail=str(e))


async def refresh_access_token(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
):
    try:
        user_id = (payload and payload.user_id) or getattr(request.state, "user_id", None) or getattr(request.state, "user", None)
        raw_token = (payload and payload.refresh_token) or request.cookies.get("refresh_token")

        if not user_id or not raw_token:
            raise HTTPException(status_code=400, detail="user_id and refresh_token are required")

        is_valid = await verify_refresh_token(user_id=user_id, raw_token=raw_token)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        new_access_token = await create_access_token(user_id=user_id)
        new_refresh_token = await create_refresh_token(user_id=user_id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        stored_ok = await update_refresh_token(
            user_id=user_id,
            refresh_token=new_refresh_token,
            expires_at=expires_at,
            hash_token=True,
        )
        if not stored_ok:
            raise HTTPException(status_code=500, detail="Could not rotate refresh token")

        _set_refresh_cookie(response, new_refresh_token)

        return {"access_token": new_access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in refresh_access_token")
        raise HTTPException(status_code=500, detail=str(e))


async def logout_user(
    request: Request,
    response: Response,
    payload: Optional[LogoutRequest] = None,
):
    try:
        user_id = (payload and payload.user_id) or getattr(request.state, "user_id", None) or getattr(request.state, "user", None)
        if user_id:
            await clear_refresh_token(user_id=user_id)
        response.delete_cookie("refresh_token", path="/")
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.exception("Unexpected error in logout_user")
        raise HTTPException(status_code=500, detail=str(e))


async def login_user(
    response: Response,
    payload: LoginRequest,
):
    """
    Authenticates an existing user with username + password.
    Returns JWT access_token and sets refresh_token cookie.
    The user_id from the token is used downstream for audit attribution.
    """
    try:
        user = await get_user_by_username(payload.username)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        from Backend.Utils.Hash import verify_password
        is_valid = await verify_password(payload.password, user["password_hash"])
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        user_id = user["user_id"]
        access_token = await create_access_token(user_id=user_id)
        refresh_token = await create_refresh_token(user_id=user_id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        await update_refresh_token(
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            hash_token=True,
        )
        _set_refresh_cookie(response, refresh_token)

        return {
            "message": "Login successful",
            "user_id": user_id,
            "username": user["username"],
            "access_token": access_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in login_user for username=%s", payload.username)
        raise HTTPException(status_code=500, detail=str(e))
