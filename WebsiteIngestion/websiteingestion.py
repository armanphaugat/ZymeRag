from pathlib import Path
BASE_DIR=Path("Data").resolve()
import asyncio
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    CacheMode,
)
from crawl4ai.content_filter_strategy import (
    PruningContentFilter
)
from crawl4ai.markdown_generation_strategy import (
    DefaultMarkdownGenerator
)
from Splitter.WebsiteSplitter import WebsiteTextSplitter
markdown_generator=DefaultMarkdownGenerator(
    content_filter=PruningContentFilter(
        threshold=0.5,
    )
)
website_splitter=WebsiteTextSplitter()
feed_dir=BASE_DIR/"Feed"
async def website_crawl(url:str):
    try:
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



