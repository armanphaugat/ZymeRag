import time
from fastapi import Request, HTTPException
import jwt
import os
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
_buckets: dict = {}
def rate_limit(capacity: int = 5, refill_rate: float = 1 / 60):
    def dependency(request: Request):
        key = f"ip:{request.client.host}"
        try:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                user_id = payload.get("user_id")
                if user_id:
                    key = f"user:{user_id}"
        except Exception:
            pass

        now = time.time()
        bucket = _buckets.get(key)
        if bucket:
            tokens = min(capacity, bucket["tokens"] + (now - bucket["last_refill"]) * refill_rate)
        else:
            tokens = capacity

        if tokens < 1:
            raise HTTPException(
                status_code=429,
                detail="Too many requests, please wait a minute",
                headers={"Retry-After": "60"}
            )

        _buckets[key] = {"tokens": tokens - 1, "last_refill": now}

    return dependency

upload_rate_limit    = rate_limit(capacity=5,  refill_rate=1/60)
