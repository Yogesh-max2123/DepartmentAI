import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth_routes import router as auth_router
from backend.api.governance_routes import router as governance_router
from backend.api.routes import router
from module2.api import router as module2_router


LOCAL_CORS_ORIGINS = (
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
)


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured_origins is None:
        return list(LOCAL_CORS_ORIGINS)

    origins: list[str] = []
    for configured_origin in configured_origins.split(","):
        origin = configured_origin.strip()
        if not origin:
            continue

        try:
            parsed_origin = urlsplit(origin)
            parsed_origin.port
        except ValueError as error:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain valid HTTP(S) origins."
            ) from error

        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.hostname
            or parsed_origin.username
            or parsed_origin.password
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
            or "*" in origin
        ):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain exact HTTP(S) origins "
                "without credentials, paths, queries, or wildcards."
            )

        origins.append(
            f"{parsed_origin.scheme.lower()}://{parsed_origin.netloc.lower()}"
        )

    if not origins:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must contain at least one exact origin."
        )

    return list(dict.fromkeys(origins))


app = FastAPI(
    title="DepartmentAI API",
    description="Agentic Academic Governance and Administrative Intelligence System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

app.include_router(auth_router)
app.include_router(router)
app.include_router(governance_router)
app.include_router(module2_router)