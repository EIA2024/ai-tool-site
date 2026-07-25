"""Tests for the Task Decomposer history CRUD service."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, TaskAnalysisHistory
from app.services.task_decomposer_history import (
    create_history,
    delete_history,
    get_history,
    list_history,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest.mark.asyncio
async def test_create_and_get_history(db):
    created = await create_history(
        db,
        raw_task="Test task",
        context="Test context",
        task_type="feature",
        model_name="deepseek-v4-flash",
        risk_hints=["data_loss"],
        risk_level="medium",
        structured_output={
            "goal": "Test goal",
            "context": ["ctx1"],
            "constraints": ["c1"],
            "done_when": ["d1"],
            "failure_cases": ["f1"],
            "verification": ["v1"],
            "missing_questions": [],
            "risk_level": "medium",
            "non_goals": [],
            "agent_prompt": "test prompt",
        },
    )
    assert created.id is not None
    assert created.raw_task == "Test task"
    assert created.task_type == "feature"
    assert created.risk_level == "medium"

    fetched = await get_history(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.structured_output["goal"] == "Test goal"


@pytest.mark.asyncio
async def test_list_history(db):
    await create_history(db, raw_task="Task A", context="", risk_hints=None, task_type="feature", model_name="m1", risk_level="low", structured_output={"goal": "a"})
    await create_history(db, raw_task="Task B", context="", risk_hints=None, task_type="bugfix", model_name="m1", risk_level="high", structured_output={"goal": "b"})

    all_records = await list_history(db)
    assert len(all_records) == 2

    filtered = await list_history(db, task_type="bugfix")
    assert len(filtered) == 1
    assert filtered[0].raw_task == "Task B"


@pytest.mark.asyncio
async def test_get_history_not_found(db):
    missing = await get_history(db, "nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_delete_history(db):
    created = await create_history(db, raw_task="Delete me", context="", risk_hints=None, task_type="feature", model_name="m1", risk_level="low", structured_output={"goal": "g"})
    deleted = await delete_history(db, created.id)
    assert deleted is True

    remaining = await get_history(db, created.id)
    assert remaining is None

    again = await delete_history(db, created.id)
    assert again is False
