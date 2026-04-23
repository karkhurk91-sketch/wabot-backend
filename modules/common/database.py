from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from modules.common.config import DATABASE_URL, SYNC_DATABASE_URL
from sqlalchemy import create_engine

# Async engine for FastAPI
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

# Sync engine for background tasks (nano-queue, lead capture, etc.)
sync_engine = create_engine(SYNC_DATABASE_URL)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session