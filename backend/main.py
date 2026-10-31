from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.scheduler_routes import router as scheduler_router
from backend.api.workflow_routes import router as workflow_router
from backend.workflow.db import initialize_workflow_db


app = FastAPI(
    title="DepartmentAI API (M.Tech.)",
    description="Agentic Academic Governance and Administrative Intelligence System - Masters' Programmes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(scheduler_router)
app.include_router(workflow_router)


@app.on_event("startup")
def initialize_workflow_database() -> None:
    initialize_workflow_db()
