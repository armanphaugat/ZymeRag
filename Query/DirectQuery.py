from  Query import BM25Query,SemanticQuery
import asyncio
bm25=BM25Query()
semantic=SemanticQuery()
async def get_all_chunks(query:str,ids:list[str]):
    bm25chunks,semanticchunks=asyncio.gather(await bm25.get_keyword_chunks_From_Feed(query,ids),await semantic.get_semantic_chunks_fromFeed(query,ids))
    return bm25chunks+semanticchunks
