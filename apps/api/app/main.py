from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes.projects import router as projects_router
from app.routes.upload import router as upload_router
from app.routes.analysis import router as analysis_router
from app.routes.datasets import router as datasets_router
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
from app.db import init_db

app = FastAPI(title="Analyst Pro API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(upload_router)
app.include_router(analysis_router)
app.include_router(datasets_router)
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


@app.on_event("startup")
def startup_event():
    init_db()


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
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc), "code": 500},
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
