import os
from dotenv import load_dotenv
import threading
_lock=threading.Lock()
import redis
import random
import asyncio
from redis import Redis
from bullmq import Queue, Worker
load_dotenv()
keys=os.getenv("GROQ_API_KEY","").split(",")
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    username=os.getenv("REDIS_USER") or None,
    password=os.getenv("REDIS_PASSWORD") or None,
    decode_responses=True
)
idx=0
exa_idx=0
tavily_idx=0
def rotate_key():
    global idx
    with _lock: 
        idx+=1

def get_key():
    with _lock:
        key = keys[idx % len(keys)]
        return key
def set_key():
    redis_client.set("nori:groq_active_key",get_key())

connection = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
}
_redis_user = os.getenv("REDIS_USER", "")
if _redis_user:
    connection["username"] = _redis_user
_redis_password = os.getenv("REDIS_PASSWORD", "")
if _redis_password:
    connection["password"] = _redis_password

queue = Queue("api-key-rotation", {"connection": connection})


async def process(job, job_token):
    rotate_key()
    set_key()


worker = Worker("api-key-rotation", process, {"connection": connection})


async def main():
    await queue.add(
        "api-key-rotation",
        {},
        {
            "repeat": {"every": 5 * 60 * 1000},
            "attempts": 3,
            "backoff": {"type": "exponential", "delay": 5000},
        },
    )
    await asyncio.Future()


asyncio.run(main())
