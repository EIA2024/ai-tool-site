from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.errors import AppError, InternalError
from app.services.cache import close_redis
from app.sse.handler import router as sse_router
from app.ws.handler import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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
_ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
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

    logging.getLogger(__name__).exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=InternalError().to_envelope())


# ── Routers ───────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")
app.include_router(sse_router, prefix="/sse")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
