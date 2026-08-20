from rank_bm25 import BM25Okapi
from pathlib import Path
import pickle
import re
import asyncio
BASE_DIR=Path("Data").resolve()
class BM25:
    def __init__(self,top_k:int=6):
        self.top_k=top_k

    async def tokenize(text:str):
        res=re.findall(r"\b\w+\b",text.lower())
        return res

    async def loadandquery(self,query:str,path:str,k:int=6):
        with open(path,"rb") as f:
            data=pickle.load(f)
        documents=data["documents"]
        bm25=data["bm25"]
        query_tokens=self.tokenize(query.lower())
        scores=bm25.get_scores(query_tokens)
        top_indices = scores.argsort()[::-1][:k]
        return [
            (documents[i], scores[i])
            for i in top_indices
        ]
        
    async def get_keyword_chunks_From_Feed(self,query:str,uuids:list[str]):
        result=[]
        paths=[]
        for uuid in uuids:
            feed_path=f"{BASE_DIR}/Feed/{uuid}"
            pathexsistence=Path(feed_path)
            if pathexsistence.exists()!=True :
                raise FileNotFoundError(f"This Directory Do not Exists {feed_path}")
            paths.append(feed_path)
        tasks=[asyncio.to_thread(self.loadandquery,self.query,path) for path in paths]
        all_result=await asyncio.gather(*tasks)
        for chunks in all_result:
            result.extend(chunks)
        if(len(result)>6):
            result.sort(key=lambda x:x[1],reverse=True)
            return result[:self.top_k]
        return result