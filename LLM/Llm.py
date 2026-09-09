from groq import AsyncGroq
import os
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

async def get_active_key():
    key = await redis_client.get("nori:groq_active_key")
    if not key:
        key = os.getenv("GROQ_API_KEY", "").split(",")[0]
    return key

async def generate_answer(question, context):
    api_key = await get_active_key()
    client = AsyncGroq(api_key=api_key) 
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