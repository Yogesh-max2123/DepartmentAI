from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.api.scheduler_routes import router as scheduler_router
from backend.api.workflow_routes import router as workflow_router
from backend.workflow.store import init_workflow_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    dialect = init_workflow_db()
    print(f"Workflow database ready ({dialect}).")
    yield


app = FastAPI(
    title="MNNIT Department Portal API (UG / PG / Ph.D.)",
    description="Agentic Academic Governance and Administrative Intelligence System - B.Tech., M.Tech. and Ph.D. Programmes",
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"https://.*\.monkeycode-ai\.live",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    from backend.workflow.store import dialect

    return {"ok": True, "workflow_db": dialect()}


app.include_router(router)
app.include_router(scheduler_router)
app.include_router(workflow_router)

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
