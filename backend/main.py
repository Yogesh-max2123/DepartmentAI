from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.scheduler_routes import router as scheduler_router


app = FastAPI(
    title="DepartmentAI API (Ph.D.)",
    description="Agentic Academic Governance and Administrative Intelligence System - Doctoral Programmes",
    version="1.0.0"
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

app.include_router(router)
app.include_router(scheduler_router)
