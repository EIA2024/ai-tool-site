from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.errors import AppError, InternalError
from app.services.cache import close_redis
from app.tool_host.discovery import get_registry
from app.tool_host.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import and validate every built-in plugin before serving traffic.
    get_registry()
    yield
    # Shutdown
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────
# Explicit allow-list only. `allow_credentials=True` + a wildcard origin is
# rejected by browsers, so we fail fast rather than deploy a broken config.
_ALLOWED_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
_ALLOWED_HEADERS = ["Content-Type", "Authorization", "Accept"]

origins = settings.cors_origins_list
if not origins or "*" in origins:
    raise RuntimeError(
        "APP_CORS_ORIGINS must be a non-empty comma-separated allow-list "
        "(wildcard '*' is not allowed with allow_credentials=True)"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=_ALLOWED_METHODS,
    allow_headers=_ALLOWED_HEADERS,
)


# ── Request body size cap ──────────────────────────────────────────────
# A tool payload is at most a few KB of text; the cap is purely an abuse
# guard so a multi-MB body is rejected before FastAPI buffers it. Covers the
# common client cases (curl, scripts, browsers all send Content-Length).
# Registered first so the security-header middleware (added below) still
# wraps the 413 response.
_MAX_BODY_BYTES = 1_000_000


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    # A client can only send a request body without Content-Length via
    # Transfer-Encoding: chunked (HTTP/1.1). Reject chunked outright —
    # every legitimate client of this API sends JSON with a Content-Length —
    # because Starlette buffers the decoded body with no size bound, so a
    # multi-MB chunked body would otherwise slip past the cap below and be
    # buffered fully in memory.
    if request.headers.get("transfer-encoding"):
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    return await call_next(request)


# ── Security response headers ─────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ── Error envelope for expected application errors ────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging

    logging.getLogger(__name__).exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(status_code=500, content=InternalError().to_envelope())


# ── Routers ───────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
