import asyncio
import re
import shutil
import sys
import os
from io import BytesIO
from typing import List, Optional

from fastapi import Form, HTTPException

from Dbhelper.website_db_helper import delete_website_from_database
from Dbhelper.pdf_db_helper import delete_content_from_database

def background_delete_content(path:str):
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
    except Exception as e:
        print(f"Error occurred while deleting content: {e}")
async def delete_id(id:str=Form()):
    global website
    try:
        directory_path = os.path.join("Data", "Content", id)
        if os.path.exists(directory_path):
            await asyncio.to_thread(background_delete_content, directory_path)
            website=0
        else:
            directory_path = os.path.join("Data", "Feed", id)
            await asyncio.to_thread(background_delete_content, directory_path)
            website=1
        if website == 1:
            await delete_website_from_database(feed_id=id)
        elif website == 0:
            await delete_content_from_database(feed_id=id)
        return {"status": "success", "message": "Content and database records successfully removed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))