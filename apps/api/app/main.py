from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.projects import router as projects_router
from app.routes.upload import router as upload_router
from app.routes.analysis import router as analysis_router
from app.routes.charts import router as charts_router

app = FastAPI(title="Analyst Pro API")

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
app.include_router(charts_router)


@app.get("/health")
def health():
    return {"status": "ok"}