"""Shared test fixtures.

- In-memory SQLite database (``StaticPool`` so every session shares the
  single connection — a plain ``:memory:`` URL otherwise gives each
  connection its own empty database).
- ``db``: an async session per test with tables recreated each test.
- ``api_client``: httpx ASGI client with the app's request-scoped DB
  dependency overridden to the test session.
"""

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base
from app.tool_host.discovery import get_registry

# Import every plugin's ORM models before tables are created. This mirrors
# alembic/env.py: plugin discovery is what registers ChatSession/ChatMessage,
# AgentPracticeRecord and TaskAnalysisHistory on Base.metadata. Without it the
# in-memory SQLite schema would only contain the Host-owned audit table.
get_registry()

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Close the pooled aiosqlite connection so its worker thread terminates
    # before the event loop closes — otherwise pytest hangs at teardown.
    await engine.dispose()


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture
async def api_client(db):
    """ASGI client whose requests share the test DB session."""

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
