from Embeddings.Embeddingmaker import Embedder
embedder=Embedder()

from pathlib import Path
BASE_DIR=Path("Data").resolve()
import asyncio

from langchain_community.vectorstores import FAISS


class SemanticQuery:
    def __init__(self):
        pass

    def load_and_search(self,path,query):
        vectorstore = FAISS.load_local(
            path, embedder.model, allow_dangerous_deserialization=True
        )
        return vectorstore.similarity_search_with_score(query, k=6)
    
    async def get_semantic_chunks_fromFeed(self,query:str,uuids:list[str],top_k:int=5):
        result=[]
        paths=[]
        for uuid in uuids:
            feed_path=f"{BASE_DIR}/Feed/{uuid}"
            pathexsistence=Path(feed_path)
            if pathexsistence.exists()!=True :
                raise FileNotFoundError(f"This Directory Do not Exists {feed_path}")
            paths.append(feed_path)
        tasks=[asyncio.to_thread(self.load_and_search,path,query) for path in paths]
        all_result=await asyncio.gather(*tasks)
        for chunks in all_result:
            result.extend(chunks)
        if(len(result)>6):
            result.sort(key=lambda x: x[1])
        return result[:top_k]
    

        