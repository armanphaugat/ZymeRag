from rank_bm25 import BM25Okapi
from pathlib import Path
import pickle
import re
import asyncio


BASE_DIR = Path("Data").resolve()


class BM25:

    def __init__(self, top_k: int = 6):
        self.top_k = top_k

    def tokenize(self, text: str):
        return re.findall(r"\b\w+\b", text.lower())

    def loadandquery(
        self,
        query: str,
        path: Path,
        k: int = 6
    ):
        with open(path, "rb") as f:
            data = pickle.load(f)
        documents = data["documents"]
        bm25 = data["bm25"]
        query_tokens = self.tokenize(query)
        scores = bm25.get_scores(query_tokens)
        top_indices = scores.argsort()[::-1][:k]
        return [
            (documents[i], scores[i])
            for i in top_indices
        ]

    async def get_keyword_chunks_From_Feed(
        self,
        query: str,
        uuids: list[str]
    ):
        result = []
        paths = []
        for uuid in uuids:
            feed_path = BASE_DIR / "Feed" / uuid
            if not feed_path.exists():
                raise FileNotFoundError(
                    f"This directory does not exist: {feed_path}"
                )
            bm25_path = feed_path / "bm25.pkl"
            if not bm25_path.exists():
                raise FileNotFoundError(
                    f"BM25 file does not exist: {bm25_path}"
                )
            paths.append(bm25_path)
        tasks = [
            asyncio.to_thread(
                self.loadandquery,
                query,
                path,
                self.top_k
            )
            for path in paths
        ]
        all_result = await asyncio.gather(*tasks)
        for chunks in all_result:
            result.extend(chunks)
        result.sort(
            key=lambda x: x[1],
            reverse=True
        )
        return result[:self.top_k]

    async def get_keyword_chunks_From_Content(
        self,
        query: str,
        uuids: list[str]
    ):
        result = []
        paths = []
        for uuid in uuids:
            content_path = BASE_DIR / "Content" / uuid
            if not content_path.exists():
                raise FileNotFoundError(
                    f"This directory does not exist: {content_path}"
                )
            bm25_path = content_path / "bm25.pkl"
            if not bm25_path.exists():
                raise FileNotFoundError(
                    f"BM25 file does not exist: {bm25_path}"
                )
            paths.append(bm25_path)
        tasks = [
            asyncio.to_thread(
                self.loadandquery,
                query,
                path,
                self.top_k
            )
            for path in paths
        ]
        all_result = await asyncio.gather(*tasks)
        for chunks in all_result:
            result.extend(chunks)
        result.sort(
            key=lambda x: x[1],
            reverse=True
        )
        return result[:self.top_k]