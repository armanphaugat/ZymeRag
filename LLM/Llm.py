from groq import AsyncGroq
import os
import asyncio
import redis.asyncio as aioredis
from dotenv import load_dotenv
load_dotenv()

redis_client = aioredis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    username=os.getenv("REDIS_USER") or None,
    password=os.getenv("REDIS_PASSWORD") or None,
    decode_responses=True,
)

_client: AsyncGroq | None = None
_client_key: str | None = None
_client_lock = asyncio.Lock()


async def get_active_key():
    key = await redis_client.get("nori:groq_active_key")
    if not key:
        key = os.getenv("GROQ_API_KEY", "").split(",")[0]
    return key


async def get_client() -> AsyncGroq:
    global _client, _client_key
    key = await get_active_key()
    if _client is None or key != _client_key:
        async with _client_lock:
            if _client is None or key != _client_key:
                _client = AsyncGroq(api_key=key)
                _client_key = key
    return _client


async def generate_answer(question, context):
    client = await get_client()
    prompt = f"""Answer the question using only the context below.
    If the answer isn't in the context, say so.
    Context:
    {context}
    Question: {question}"""
    response = await client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content