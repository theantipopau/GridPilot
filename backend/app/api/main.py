from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT
from app.api import (
    audit,
    blocking,
    change_sets,
    composites,
    dashboard,
    findings,
    ingest,
    reference,
    room_constraints,
    solver,
    teachers,
    timetable,
    timetable_entries,
)

app = FastAPI(title="GridPilot API")

# Local dev only - the Vite dev server and this API both run on localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(reference.router, prefix="/api")
app.include_router(timetable.router, prefix="/api")
app.include_router(timetable_entries.router, prefix="/api")
app.include_router(findings.router, prefix="/api")
app.include_router(composites.router, prefix="/api")
app.include_router(change_sets.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(teachers.router, prefix="/api")
app.include_router(blocking.router, prefix="/api")
app.include_router(room_constraints.router, prefix="/api")
app.include_router(solver.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Serves the built frontend (npm run build -> frontend/dist) from the same
# process/port as the API - see docs/packaging.md Phase 1. Mounted last, and
# only if the directory exists, so normal dev (two servers, no dist/ built)
# is completely unaffected.
_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
