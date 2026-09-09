from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Query.DirectQuery import get_all_chunks
from LLM.Llm import generate_answer
from fastapi import Query
router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    ids: list[str]
    fallback_threshold: float = 0.5
    fallback_provider: str = "both"
    max_web_results: int = 5




async def build_context(chunks: list[tuple]) -> str:
    texts = []
    for doc, _score in chunks:
        if hasattr(doc, "page_content"):
            texts.append(doc.page_content)
        else:
            texts.append(str(doc))
    return "\n\n".join(texts)


async def query_endpoint(question:str=Query(...),ids:list[str]=Query(...)):
    if question is None or not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        chunks = await get_all_chunks(question,ids)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant chunks found for this query")

    context = await build_context(chunks)

    try:
        answer = await generate_answer(question, context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq generation failed: {e}")

    return answer