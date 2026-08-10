"""Local dev server that runs without Docker.

Falls back to a file-based SQLite database when DATABASE_URL is not set
(so the whole stack works without Postgres/Redis), then starts uvicorn with
auto-reload. Run from anywhere in the repo:

    python backend/run_dev.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Anchor the dev database to this file's directory so it does not depend on
# the CWD the server happens to be launched from.
_BACKEND_DIR = Path(__file__).resolve().parent
os.environ.setdefault(
    "DATABASE_URL", f"sqlite+aiosqlite:///{(_BACKEND_DIR / 'dev.db').as_posix()}"
)

# Make the backend package importable regardless of CWD.
sys.path.insert(0, str(_BACKEND_DIR))


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
    import importlib

    import uvicorn
    from uvicorn.supervisors.statreload import StatReload

    asyncio.run(_init_db())
    # NOTE: with reload=True the child process re-imports app.main directly;
    # the DATABASE_URL override above is inherited via os.environ.
    #
    # Reload hardening (Windows + OneDrive-synced repo):
    # - Watch only app/ so writing tests or the dev.db never triggers a reload.
    # - Force the polling StatReload: this uvicorn build picks WatchFiles by
    #   default whenever `watchfiles` is installed, and WatchFiles has a known
    #   bug on Windows where a detected change shuts the worker down but never
    #   spawns the replacement, wedging the port (observed twice). StatReload
    #   polls mtimes and restarts reliably. Only the reloader process needs
    #   the patch; the worker imports the app normally.
    #   (uvicorn.main is shadowed by a click Command on the package, so grab
    #   the real module via sys.modules.)
    uvicorn_main = importlib.import_module("uvicorn.main")
    uvicorn_main.ChangeReload = StatReload
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(_BACKEND_DIR / "app")],
        reload_includes=["*.py"],
        reload_excludes=[
            "**/tests/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "**/dev.db",
        ],
    )


if __name__ == "__main__":
    main()
