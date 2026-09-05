import asyncio
from Query.BM25Query import BM25
from Query.SemanticQuery import SemanticQuery
from Query.WebSearchFallback import WebSearchFallback

bm25 = BM25()
semantic = SemanticQuery()
web_fallback = WebSearchFallback()


async def get_all_chunks(query: str, ids: list[str]):
    bm25chunks, semanticchunks = await asyncio.gather(
        bm25.get_keyword_chunks_From_Feed(query, ids),
        semantic.get_semantic_chunks_fromFeed(query, ids)
    )
    return bm25chunks + semanticchunks


async def get_all_chunks_with_fallback(
    query: str,
    ids: list[str],
    fallback_threshold: float = 0.5,
    fallback_provider: str = "both",
    max_web_results: int = 5
):

    kb_chunks = await get_all_chunks(query, ids)
    return await web_fallback.evaluate_and_fallback(
        query=query,
        kb_chunks=kb_chunks,
        threshold=fallback_threshold,
        provider=fallback_provider,
        max_results=max_web_results
    )

