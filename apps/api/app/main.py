import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes.projects import router as projects_router
from app.routes.upload import router as upload_router
from app.routes.analysis import router as analysis_router
from app.routes.charts import router as charts_router
from app.routes.explore import router as explore_router
from app.routes.ml import router as ml_router
from app.routes.chat import router as chat_router
from app.routes.reports import router as reports_router
from app.routes.pivot import router as pivot_router
from app.routes.cohorts import router as cohorts_router
from app.routes.stats import router as stats_router
from app.routes.query import router as query_router
from app.routes.features import router as features_router
from app.routes.analysis_stream import router as analysis_stream_router
from app.routes.auth import router as auth_router

# ── Structured logging setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("analyistpro")

# ── Optional Sentry integration ───────────────────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production"),
        )
        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry-sdk not installed; skipping Sentry integration")

# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    from app.db import init_db
    init_db()
    logger.info("Database initialized")
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
    if supabase_url:
        logger.info(f"Supabase JWKS endpoint: {supabase_url}/auth/v1/.well-known/jwks.json")
    else:
        logger.warning("SUPABASE_URL is not set — JWT verification via JWKS will fail!")
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if jwt_secret:
        logger.info(f"Legacy SUPABASE_JWT_SECRET loaded ({len(jwt_secret)} chars) — HS256 fallback active")
    yield  # Application runs here


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AnalystPro API",
    version="2.0.0",
    description="AI-powered data analytics platform",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request timing middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        f"method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={duration_ms}"
    )
    return response

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(projects_router)
app.include_router(upload_router)
app.include_router(analysis_router)
app.include_router(charts_router)
app.include_router(explore_router)
app.include_router(ml_router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(pivot_router)
app.include_router(cohorts_router)
app.include_router(stats_router)
app.include_router(query_router)
app.include_router(features_router)
app.include_router(analysis_stream_router)
app.include_router(auth_router)

# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "Bad request", "detail": str(exc), "code": 400},
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError):
    return JSONResponse(
        status_code=400,
        content={"error": "Missing key", "detail": f"Column or key not found: {exc}", "code": 400},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc), "code": 500},
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
