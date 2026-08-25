import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("Data").resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or ""

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL or SUPABASE_DB_URL is not set in environment or .env file. "
        "Please specify your Supabase PostgreSQL connection string."
    )

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
