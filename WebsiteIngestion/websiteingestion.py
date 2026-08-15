from pathlib import Path
BASE_DIR=Path("Data").resolve()
import asyncio
import uuid
import shutil
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
from Embeddings.Embeddingmaker import EmbeddingMaker
markdown_generator=DefaultMarkdownGenerator(
    content_filter=PruningContentFilter(
        threshold=0.5,
    )
)
website_splitter=WebsiteTextSplitter()
embedding_maker=EmbeddingMaker()
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
        vectorstore=FAISS.from_documents(chunks,embedding_maker)
        vectorstore.save_local(str(feed_path))
        database_saved=await save_website_to_database(url,id)
        if database_saved:
            print(f"Website {url} ingested and saved to database with ID: {id}")
            return None
        return id
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
        print(f"Website {url} updated and saved to database with ID: {id}")
        return None
    else:
        print("No markdown content to process.")
        return None



