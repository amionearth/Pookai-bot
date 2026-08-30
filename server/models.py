"""
server/models.py — request/response Pydantic models for the API layer.

Mirrors the four sequential web app steps:
  1. /api/designs/generate      → 3 image candidates
  2. /api/designs/select        → confirm which one
  3. /api/designs/vectorize     → run the CV pipeline, return traceable waypoints
  4. /api/robot/send            → hand the path off to the ML/control service
Plus:
  - /api/camera/stream          → MJPEG video stream (no Pydantic model needed)
  - /api/health                 → service health
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ── Step 1: Generate ──────────────────────────────────────────────────────────

PetalCount = Literal[4, 5, 6, 8, 10, 12]
ColorCount = Literal[2, 3, 4, 5]
LayerCount = Literal[1, 2, 3]


class GenerateRequest(BaseModel):
    """What the user told us about the design they want."""
    petal_count: PetalCount = Field(6)
    layer_count: LayerCount = Field(2)
    color_count: ColorCount = Field(3)
    free_text:   str = Field("", max_length=500)
    style:       Optional[str] = Field("traditional")


class DesignOut(BaseModel):
    """API view of a Pookalam design candidate. The image is a data URL so the
    frontend can drop it directly into <img src=...>."""
    id: str
    title: str
    description: str
    petal_count: int
    layer_count: int
    color_count: int
    free_text:   str = ""

    image_data_url: str
    image_mime: str = "image/png"

    drawable: bool
    source: str                       # "gemini" | "stub"


class GenerateResponse(BaseModel):
    designs: List[DesignOut]


# ── Step 2: Select ────────────────────────────────────────────────────────────

class SelectRequest(BaseModel):
    design_id: str


class SelectResponse(BaseModel):
    selected_id: str
    message: str


# ── Step 3: Vectorize ─────────────────────────────────────────────────────────

class VectorizeRequest(BaseModel):
    design_id: str
    # Real-world edge length of the drawing area in centimetres. The whole
    # traced image gets scaled to fit inside this square. Default 60 cm is
    # a typical pookalam — adjust to your physical floor space.
    canvas_cm: float = Field(60.0, gt=0, le=300)


class VectorizeError(BaseModel):
    """Why vectorization failed, in plain terms suitable for end-user display."""
    code: Literal[
        "design_not_found",
        "decode_failed",
        "no_circle_detected",
        "too_many_waypoints",
        "no_contours_found",
    ]
    message: str


class PathWaypoint(BaseModel):
    x:  float   # centimetres from the design centre
    y:  float   # centimetres
    pen: Literal[0, 1]


class VectorizeResponse(BaseModel):
    design_id: str
    canvas_cm: float
    status: Literal["ok", "failed"]

    # Geometry
    center_x_cm: float
    center_y_cm: float
    radius_cm:   float

    # Path (only populated when status == "ok")
    waypoints: List[PathWaypoint] = []

    # Estimates (only populated when status == "ok")
    estimated_waypoints:        int   = 0
    estimated_drawing_time_sec: int   = 0

    # Debug — base64-encoded preview images for the side-by-side in the UI
    original_png_data_url: Optional[str] = None
    traced_png_data_url:   Optional[str] = None

    # On failure, this is set instead of waypoints/etc.
    error: Optional[VectorizeError] = None


# ── Step 4: Send to Robot ─────────────────────────────────────────────────────

class RobotSendRequest(BaseModel):
    design_id: str
    # Send the waypoints inline so the web app doesn't depend on shared
    # state with the control service — fully self-contained payload.
    waypoints: List[PathWaypoint]
    canvas_cm: float


class RobotSendResponse(BaseModel):
    accepted: bool
    design_id: str
    message: str
    # Optional status from the control service, if it exposes one
    control_service_status: Optional[str] = None


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    ai_available: bool
    mode: Literal["ai", "no_key"]
    provider: str = "pollinations"      # "pollinations" | "gemini"
