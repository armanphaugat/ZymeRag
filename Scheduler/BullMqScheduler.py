import asyncio
import os
import sys

from bullmq import Queue, Worker
from WebsiteIngestion.websiteingestion import update_website
from Dbhelper.website_db_helper import get_urls_from_database
from filelock import FileLock
connection = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
}

queue = Queue("Chunks Updation", {"connection": connection})


async def process(job, job_token):
    urls=await get_urls_from_database()
    for url,id in urls:
        try:
            await update_website(url,id)
        except Exception as e:
            print(f"Error occurred while ingesting website {url}: {e}")


worker = Worker("Chunks Updation", process, {"connection": connection})


async def main():
    await queue.add(
        "Chunks Updation",
        {},
        { 
            "repeat": {"every": 24*60* 60 * 1000},
            "attempts": 3,
            "backoff": {"type": "exponential", "delay": 10000},
        },
    )
    await asyncio.Future()


asyncio.run(main())
