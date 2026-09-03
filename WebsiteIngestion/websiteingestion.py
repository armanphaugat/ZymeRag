from pathlib import Path
BASE_DIR=Path("Data").resolve()
import asyncio
import uuid
import shutil
import anyio
from langchain_community.vectorstores import FAISS
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    CacheMode,
)
from Dbhelper.website_db_helper import save_website_to_database
from crawl4ai.content_filter_strategy import (
    PruningContentFilter
)
from crawl4ai.markdown_generation_strategy import (
    DefaultMarkdownGenerator
)
from Splitter.WebsiteSplitter import WebsiteTextSplitter
from Embeddings.Embeddingmaker import Embedder
from rank_bm25 import BM25Okapi
import pickle
import re
markdown_generator=DefaultMarkdownGenerator(
    content_filter=PruningContentFilter(
        threshold=0.5,
    )
)
website_splitter=WebsiteTextSplitter()
embedding_maker=Embedder()
config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav","footer","header","style","script"],
            exclude_external_links=False,
            remove_overlay_elements=True,
            remove_consent_popups=True,
            wait_until="domcontentloaded",
            scan_full_page=True,
            markdown_generator=markdown_generator,
    )
feed_dir=BASE_DIR/"Feed"

def build_and_save_bm25(chunks, path):
    tokenized_documents = [
        re.findall(
            r"\b\w+\b",
            chunk.page_content.lower()
        )
        for chunk in chunks
    ]
    bm25 = BM25Okapi(tokenized_documents)
    with open(path, "wb") as f:
        pickle.dump(
            {
                "documents": chunks,
                "bm25": bm25
            },
            f
        )
async def website_crawl(url:str):
    try:
        
        async with AsyncWebCrawler() as crawler:
            result=await crawler.arun(url,config=config)
        if result.success:
            print("Successfully crawled the website.")
            return result.markdown.fit_markdown
            
        else:
            print("Failed to crawl the website.")
            return None
    except Exception as e:
        print(f"Error occurred while crawling the website: {e}")
        return None

async def ingest_website(url:str):
    markdown=await website_crawl(url)
    if markdown:
        chunks=website_splitter.split(markdown)
        id=str(uuid.uuid4())
        feed_path=feed_dir/f"{id}"
        feed_path.mkdir(parents=True,exist_ok=True)
        bm25_path=feed_path/"bm25.pkl"
        await asyncio.to_thread(build_and_save_bm25,chunks,bm25_path)
        vectorstore=FAISS.from_documents(chunks,embedding_maker)
        vectorstore.save_local(str(feed_path))
        database_saved = await save_website_to_database(url=url, feed_id=id, chunks=len(chunks))
        if database_saved:
            print(f"Website {url} ingested and saved to database with ID: {id}")
            return id
        return None
    else:
        print("No markdown content to process.")
        return None

async def update_website(url:str,id:str):
    markdown=await website_crawl(url)
    if markdown:
        chunks=website_splitter.split(markdown)
        feed_path=feed_dir/f"{id}"
        temp_path=feed_dir/f"{id}__temp"
        temp_path.mkdir(parents=True,exist_ok=True)
        vectorstore=FAISS.from_documents(chunks,embedding_maker)
        vectorstore.save_local(str(temp_path))
        if feed_path.exists():
            shutil.rmtree(feed_path)
        temp_path.rename(feed_path)
        await update_website_last_crawled(feed_id=id, chunks=len(chunks))
        print(f"Website {url} updated and saved to database with ID: {id}")
        return id
    else:
        print("No markdown content to process.")
        return None

async def delete_website(id:str):
    try:
        feed_path=feed_dir/f"{id}"
        if feed_path.exists():
            await anyio.to_thread.run_sync(shutil.rmtree, feed_path)
            print(f"Feed with ID: {id} deleted successfully.")
            return True
        else:
            print(f"Feed with ID: {id} does not exist.")
            return False
    except Exception as e:
        print(f"Error occurred while deleting Feed: {e}")
        return False



