from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import reference, timetable

app = FastAPI(title="Sophia College Timetable Tool API")

# Local dev only - the Vite dev server and this API both run on localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(reference.router, prefix="/api")
app.include_router(timetable.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
