"""Local dev server that runs without Docker.

Falls back to a file-based SQLite database when DATABASE_URL is not set
(so the whole stack works without Postgres/Redis), then starts uvicorn with
auto-reload. Run from the ``backend/`` directory:

    python run_dev.py
"""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

# Make the backend package importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent))


async def _init_db() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.models import Base

    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def main() -> None:
    import uvicorn

    asyncio.run(_init_db())
    # NOTE: with reload=True the child process re-imports app.main directly;
    # the DATABASE_URL override above is inherited via os.environ.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
