from Embeddings.Embeddingmaker import Embedder
embedder=Embedder()

from pathlib import Path
BASE_DIR=Path("Data").resolve()
import asyncio
import uuid
import shutil
import anyio
from langchain_community.vectorstores import FAISS


class Query:
    def __init__(self,uuid:list[str]):
        self.uuid=uuid

    async def get_semantic_chunks_fromFeed(self,per_uuid:int=5,top_k:int=5):
        result=[]
        for uuid in self.uuid:
            vectorstore=FAISS.load_local(
                f"Data/Feed/{uuid}",
                embedder.model,
                allow_dangerous_deserialization=True
            )
            chunks=await asyncio.to_thread(vectorstore.similarity_search_with_score,self.query,k=3)
            result.extend(chunks)
        if(len(result)>6):
            result.sort(key=lambda x:x[1])
            return result[:top_k]
        return result

        