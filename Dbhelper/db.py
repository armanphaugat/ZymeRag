from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from Dbhelper.config import ASYNC_DATABASE_URL

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=False,
    pool_size=20,
    max_overflow=40,
    pool_recycle=300,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
)

AsyncDB = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Placeholder init_db for async startup compatibility."""
    pass
