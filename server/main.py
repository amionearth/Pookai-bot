"""
server/main.py — PookalBot FastAPI application.

Scope: the web app layer only (Steps 1-4 of the UX). The ML/control service
that drives the actual robot is a separate process — see the project
roadmap, steps 4-7.

Start (dev):
    set GEMINI_API_KEY=...               # PowerShell:  $env:GEMINI_API_KEY = "..."
    python -m uvicorn server.main:app --host 0.0.0.0 --reload

Start (hackathon demo, on the Pi):
    setx GEMINI_API_KEY "..."            # one-time
    python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
    # then open http://raspberrypi.local:8000 from any device on the same WiFi

API docs: http://<host>:8000/docs
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ai.generator import ai_available
from ai.gemini_client import current_provider_name
from server.models import HealthResponse
from server.routes.designs import router as designs_router
from server.routes.camera  import router as camera_router
from server.routes.robot   import router as robot_router
from server.routes.live    import router as live_router
from server.routes.calibration import router as calibration_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="PookalBot API",
    description=(
        "Web app layer for the AI-Powered Pookalam robot. "
        "Endpoints cover Step 1 (generate) → Step 2 (select) → Step 3 "
        "(vectorize) → Step 4 (send to robot), plus a live camera stream."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow all local origins and devices on WiFi ───────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(designs_router)
app.include_router(camera_router)
app.include_router(robot_router)
app.include_router(live_router)
app.include_router(calibration_router)

# ── Serve the existing static frontend ───────────────────────────────────────
_static = Path(__file__).parent.parent / "web" / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(_static / "index.html"), headers={"Cache-Control": "no-cache"})

    @app.get("/style.css", include_in_schema=False)
    async def serve_style():
        return FileResponse(str(_static / "style.css"), media_type="text/css", headers={"Cache-Control": "no-cache"})

    @app.get("/app.js", include_in_schema=False)
    async def serve_app():
        return FileResponse(str(_static / "app.js"), media_type="application/javascript", headers={"Cache-Control": "no-cache"})

    from server.routes.designs import generate_design_direct, GenerateDesignDirectRequest
    @app.post("/api/generate-design", include_in_schema=False)
    async def api_generate_design(req: GenerateDesignDirectRequest):
        return await generate_design_direct(req)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Service health check — reports which image provider is active."""
    available = ai_available()
    return HealthResponse(
        status="ok",
        service="pookalbot",
        ai_available=available,
        mode="ai" if available else "no_key",
        provider=current_provider_name(),
    )
