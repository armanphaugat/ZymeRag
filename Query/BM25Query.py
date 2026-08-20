from rank_bm25 import BM25Okapi
from pathlib import Path
import pickle
import re
import asyncio
BASE_DIR=Path("Data").resolve()
class BM25:
    def __init__(self,uuids:list[str],query:str,top_k:int=6):
        self.uuids=uuids
        self.query=query

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
        
    async def get_keyword_chunks_From_Feed(self):
        result=[]
        for uuid in self.uuids:
            feed_path=f"{BASE_DIR}/Feed/{uuid}"
            pathexsistence=Path(feed_path)
            if pathexsistence.exists()!=True :
                raise FileNotFoundError(f"This Directory Do not Exists {feed_path}")
            chunks=await asyncio.to_thread(self.loadandquery,self.query,feed_path)
            result.extend(chunks)
        if(len(result)>6):
            result.sort(key=lambda x:x[1],reverse=True)
            return result[:self.top_k]
        return result