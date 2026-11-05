"""
FastAPI backend entry point.

Run from the Fitness/ directory with:

    .venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

Binding to 127.0.0.1 (not 0.0.0.0) keeps this off the network per the
README's "Bind local backend services to localhost by default" rule.
CORS is restricted to the local Vite dev server / built frontend
origin for the same reason — this API is not meant to be reachable
from anywhere but this machine's browser.
"""

import os
import sys
from pathlib import Path

# Make `src` and `backend` importable as top-level packages regardless
# of the caller's working directory (mirrors the fix applied to
# src/database.py, src/excel_generator.py, coach.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.security import LocalOnlyMiddleware

from src.database import create_database
from src.paths import make_private
from src.data_admin import auto_backup_if_due

from backend.routers import (
    overview,
    workouts,
    running,
    nutrition,
    recovery,
    goals,
    planner,
    settings,
    coach,
    imports,
    data,
)

DEV_MODE = os.environ.get("KAISEN_DEV") == "1"

app = FastAPI(
    title="KaisenOS",
    description="Local-only backend. Not intended to be exposed beyond localhost.",
    # The interactive API docs are only available in developer mode.
    docs_url="/docs" if DEV_MODE else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEV_MODE else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
# Added last = runs first: host/origin checks and security headers on everything.
app.add_middleware(LocalOnlyMiddleware)


@app.on_event("startup")
def on_startup():
    # Safe to call on every startup: create_database() / run_migrations()
    # only ever CREATE TABLE IF NOT EXISTS, never drop or alter.
    make_private()  # owner-only data folder and files
    create_database()
    auto_backup_if_due()  # daily safety copy, newest 10 kept


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(overview.router)
app.include_router(workouts.router)
app.include_router(running.router)
app.include_router(nutrition.router)
app.include_router(recovery.router)
app.include_router(goals.router)
app.include_router(planner.router)
app.include_router(settings.router)
app.include_router(coach.router)
app.include_router(imports.router)
app.include_router(data.router)


# --------------------------------------------------
# The dashboard itself (built frontend), served from the same address.
# Run `npm run build` in frontend/ (setup.sh does this). In development,
# the Vite dev server on :5173 is used instead.
# --------------------------------------------------

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def dashboard(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return JSONResponse(
            {"detail": "Dashboard not built. Run ./setup.sh (or `npm run build` in frontend/)."}, status_code=404
        )
    # Only files inside dist/ can be served (no path traversal); anything
    # else is a dashboard route, so return the app shell.
    candidate = (FRONTEND_DIST / path).resolve()
    if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(index, media_type="text/html")
