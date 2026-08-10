from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# pool_pre_ping: on Postgres a pooled connection can go stale after the DB
# restarts/idles out; pre-ping on checkout surfaces that as a fresh reconnect
# instead of a mid-request "server closed the connection" error. (No-op for
# the aiosqlite dev fallback.)
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
