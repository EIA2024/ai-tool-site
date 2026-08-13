"""Local dev server that runs without Docker.

Falls back to a file-based SQLite database when DATABASE_URL is not set
(so the whole stack works without Postgres/Redis), then runs uvicorn with
auto-restart. Run from anywhere in the repo:

    python backend/run_dev.py

Auto-restart is a tiny in-process supervisor rather than uvicorn's own
reloader: uvicorn's reloaders (WatchFiles and StatReload alike) have a
Windows bug where a detected change shuts the worker down but the
replacement never spawns, wedging the port. Here the server runs as a plain
subprocess (reload=False) and the supervisor restarts it whenever any
`app/**/*.py` mtime changes — the subprocess exit releases the port and the
restart binds fresh, which is reliable on Windows.
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Anchor the dev database to this file's directory so it does not depend on
# the CWD the server happens to be launched from.
_BACKEND_DIR = Path(__file__).resolve().parent
os.environ.setdefault(
    "DATABASE_URL", f"sqlite+aiosqlite:///{(_BACKEND_DIR / 'dev.db').as_posix()}"
)

# Make the backend package importable regardless of CWD.
sys.path.insert(0, str(_BACKEND_DIR))

# Files whose changes restart the dev server (tests/__pycache__/dev.db are
# deliberately excluded so writing them never triggers a reload).
_WATCH_GLOBS = ("app/**/*.py",)
_EXTRA_WATCH = (
    Path(__file__).resolve(),  # run_dev.py itself
    _BACKEND_DIR / ".env",
)
_POLL_SECONDS = 0.4
_CRASH_BACKOFF_SECONDS = 1.0
_MAX_CONSECUTIVE_CRASHES = 10


async def _init_db() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.models import Base
    from app.tool_host.discovery import get_registry

    # Import every plugin's ORM models before table creation so the SQLite
    # fallback schema includes the plugin tables (same as alembic/env.py and
    # the test conftest).
    get_registry()

    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def _watched_files() -> list[Path]:
    files = list(_EXTRA_WATCH)
    for pattern in _WATCH_GLOBS:
        files.extend(_BACKEND_DIR.glob(pattern))
    return files


def _snapshot() -> dict[str, int]:
    return {str(p): p.stat().st_mtime_ns for p in _watched_files() if p.exists()}


def _run_worker() -> None:
    """Worker mode (``--reload-worker``): plain uvicorn, no reloader.

    Running without uvicorn's own reloader sidesteps the Windows bug where a
    detected change shuts the worker down but never spawns the replacement,
    wedging the port. The supervisor (``_supervise``) is the reloader
    instead: it runs this worker as a subprocess and restarts it, so the port
    is released by process exit and re-bound fresh.
    """
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


def _supervise() -> None:
    """Start the worker, watch for changes, restart on change or crash."""
    snapshot = _snapshot()
    crashes = 0
    while True:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--reload-worker"],
            cwd=_BACKEND_DIR,
        )
        interrupted = False
        try:
            changed = False
            while proc.poll() is None:
                try:
                    time.sleep(_POLL_SECONDS)
                except KeyboardInterrupt:
                    # Ctrl+C reached both this process and the worker (same
                    # console); stop the supervisor once the worker is down.
                    interrupted = True
                    break
                if _snapshot() != snapshot:
                    changed = True
                    break
        finally:
            # Worker down (or being taken down) -> port is released.
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        if interrupted:
            print("\n[run_dev] stopped.", flush=True)
            return
        if changed:
            print("\n[run_dev] change detected — restarting...\n", flush=True)
            crashes = 0
            snapshot = _snapshot()
            continue

        code = proc.returncode
        if code == 0:
            print("[run_dev] dev server exited.", flush=True)
            return
        crashes += 1
        if crashes > _MAX_CONSECUTIVE_CRASHES:
            print(
                f"[run_dev] server crashed {crashes}x in a row; giving up.",
                flush=True,
            )
            return
        print(f"[run_dev] server exited with code {code}; restarting...", flush=True)
        time.sleep(_CRASH_BACKOFF_SECONDS)


def main() -> None:
    asyncio.run(_init_db())
    if "--reload-worker" in sys.argv:
        _run_worker()
        return
    _supervise()


if __name__ == "__main__":
    main()
