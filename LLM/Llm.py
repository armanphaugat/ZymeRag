from groq import AsyncGroq
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=GROQ_API_KEY)

async def generate_answer(question, context):
    prompt = f"""Answer the question using only the context below.
If the answer isn't in the context, say so.

Context:
{context}

Question: {question}"""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content