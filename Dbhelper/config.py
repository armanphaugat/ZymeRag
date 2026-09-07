import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("Data").resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or ""

if not DATABASE_URL:
    # Graceful fallback for local tests and unconfigured environments
    print("[Dbhelper] Warning: DATABASE_URL / SUPABASE_DB_URL not set. Falling back to default localhost Postgres.")
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
