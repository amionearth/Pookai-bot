"""
server/routes/designs.py — /api/designs/* endpoints (Steps 1-3 of the web app).

  POST /api/designs/generate    Step 1 — 3 Pookalam candidates from Gemini
  POST /api/designs/select      Step 2 — user picks one
  GET  /api/designs/current     —       what the user has selected so far
  POST /api/designs/vectorize   Step 3 — run the CV pipeline, return waypoints

The route is async so the event loop stays free during the (potentially ~10s)
Gemini image-generation network waits.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from ai.generator import generate_designs_async, ai_available
from ai.gemini_client import current_provider_name
from ai.models import DesignCandidate, DesignRequest
from server.models import (
    DesignOut, GenerateRequest, GenerateResponse,
    PathWaypoint, SelectRequest, SelectResponse,
    VectorizeError, VectorizeRequest, VectorizeResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/designs", tags=["designs"])

# In-memory state (single-session hackathon setup; swap to DB later)
_last_candidates: list[DesignCandidate] = []
_selected_design: Optional[DesignCandidate] = None


# ── Internal helper ──────────────────────────────────────────────────────────

def _to_out(d: DesignCandidate) -> DesignOut:
    return DesignOut(
        id=d.id,
        title=d.title,
        description=d.description,
        petal_count=d.petal_count,
        layer_count=d.layer_count,
        color_count=d.color_count,
        free_text=d.free_text,
        image_data_url=f"data:{d.image_mime};base64,{d.image_b64}",
        image_mime=d.image_mime,
        drawable=d.drawable,
        source=d.source,
    )


# ── Step 1: Generate ─────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, summary="Generate Pookalam design candidates")
async def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Generate 2-3 Pookalam design candidates using Gemini image generation.

    The server-side developer prompt (see ai/gemini_client.py) is the actual
    set of constraints the image has to satisfy; the user only ever supplies
    {petal_count, layer_count, color_count, free_text}.

    Returns 503 if GEMINI_API_KEY (or legacy AI_API_KEY) is not set.
    Returns 502 if Gemini produced no usable images.
    """
    if not ai_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key not configured. "
                "Set the GEMINI_API_KEY environment variable on the server "
                "(e.g. setx GEMINI_API_KEY ...; uvicorn server.main:app --host 0.0.0.0)."
            ),
        )

    global _last_candidates
    ai_req = DesignRequest(
        petal_count=req.petal_count,
        layer_count=req.layer_count,
        color_count=req.color_count,
        free_text=req.free_text,
        style=req.style or "traditional",
    )
    candidates = await generate_designs_async(ai_req, n=3)
    if not candidates:
        provider = current_provider_name()
        raise HTTPException(
            status_code=502,
            detail=(
                f"{provider} returned no usable images. Check server logs — "
                f"the request may have been blocked by the provider's safety "
                f"filters, or every candidate failed validation."
            ),
        )
    _last_candidates = candidates
    return GenerateResponse(designs=[_to_out(d) for d in candidates])


class GenerateDesignDirectRequest(BaseModel):
    theme: str = ""
    symmetry: str = "8-fold"
    complexity: str = "medium"
    style: str = "traditional"


@router.post("/generate-design")
async def generate_design_direct(req: GenerateDesignDirectRequest):
    """Direct compatibility endpoint for frontend AI Designer."""
    global _last_candidates
    sym_num = 8
    try:
        sym_num = int("".join(c for c in req.symmetry if c.isdigit()) or "8")
    except Exception:
        pass
    if sym_num not in (4, 5, 6, 8, 10, 12):
        sym_num = 8

    ai_req = DesignRequest(
        petal_count=sym_num,
        layer_count=2 if req.complexity == "medium" else (3 if req.complexity == "detailed" else 1),
        color_count=3,
        free_text=req.theme or "Traditional Kerala Lotus Pookalam",
        style=req.style or "traditional",
    )
    candidates = await generate_designs_async(ai_req, n=3)
    _last_candidates = candidates

    from ai.gemini_client import build_svg_and_png
    results = []
    for d in candidates:
        svg_code, _ = build_svg_and_png({
            "rings": [420, 280, 160],
            "petals": d.petal_count,
            "inner_petals": d.petal_count,
            "outer_petals": d.petal_count,
        }, style=req.style or "traditional")
        results.append({
            "id": d.id,
            "name": d.title,
            "description": d.description,
            "symmetry": f"{d.petal_count}-fold",
            "complexity": req.complexity,
            "motifs": ["lotus", "mandala", "onam"],
            "svg": svg_code,
        })
    return {"ok": True, "designs": results}


# ── Step 2: Select ────────────────────────────────────────────────────────────

@router.post("/select", response_model=SelectResponse, summary="Select a design")
async def select_design(req: SelectRequest) -> SelectResponse:
    """Store the user's selected design for later vectorization + drawing."""
    global _selected_design
    match = next((d for d in _last_candidates if d.id == req.design_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Design {req.design_id!r} not found. Generate designs first.",
        )
    _selected_design = match
    return SelectResponse(
        selected_id=match.id,
        message=f"Design '{match.title}' selected.",
    )


@router.get("/current", response_model=Optional[DesignOut], summary="Get currently selected design")
async def current_design() -> Optional[DesignOut]:
    """Return the currently selected design, or null if none selected yet."""
    if _selected_design is None:
        return None
    return _to_out(_selected_design)


# ── Step 3: Vectorize ─────────────────────────────────────────────────────────

@router.post("/vectorize", response_model=VectorizeResponse, summary="Vectorize the selected design")
async def vectorize(req: VectorizeRequest) -> VectorizeResponse:
    """
    Run the selected design's image through the CV pipeline and return a
    drawable waypoint list in centimetres, plus a couple of preview images
    (original + traced overlay) for the side-by-side in the web UI.

    If the design hasn't been selected yet, falls back to the most recent
    candidate matching req.design_id in the generation cache.
    """
    match = _selected_design
    if match is None or match.id != req.design_id:
        match = next((d for d in _last_candidates if d.id == req.design_id), None)
    if match is None:
        return VectorizeResponse(
            design_id=req.design_id,
            canvas_cm=req.canvas_cm,
            status="failed",
            center_x_cm=0.0, center_y_cm=0.0, radius_cm=0.0,
            error=VectorizeError(
                code="design_not_found",
                message="That design isn't in the current session. "
                        "Generate and select it first.",
            ),
        )

    try:
        image_bytes = base64.b64decode(match.image_b64)
    except Exception as exc:
        return VectorizeResponse(
            design_id=req.design_id,
            canvas_cm=req.canvas_cm,
            status="failed",
            center_x_cm=0.0, center_y_cm=0.0, radius_cm=0.0,
            error=VectorizeError(
                code="decode_failed",
                message=f"Couldn't decode the selected image: {exc}",
            ),
        )

    # Lazy import — the CV pipeline is heavy and not all routes need it.
    from cv.vectorize import vectorize_image
    import asyncio

    try:
        # Offload to a thread so the event loop stays free during the
        # CPU-bound OpenCV work — keeps /api/health and other endpoints
        # responsive even while vectorize is grinding.
        result = await asyncio.to_thread(
            vectorize_image,
            image_bytes=image_bytes,
            canvas_cm=req.canvas_cm,
        )
    except RuntimeError as exc:
        msg = str(exc)
        code = "no_contours_found"
        if "circle" in msg.lower():
            code = "no_circle_detected"
        elif "waypoint" in msg.lower() or "too many" in msg.lower():
            code = "too_many_waypoints"
        return VectorizeResponse(
            design_id=req.design_id,
            canvas_cm=req.canvas_cm,
            status="failed",
            center_x_cm=0.0, center_y_cm=0.0, radius_cm=0.0,
            error=VectorizeError(code=code, message=msg),
        )

    return VectorizeResponse(
        design_id=req.design_id,
        canvas_cm=req.canvas_cm,
        status="ok",
        center_x_cm=result["center_x_cm"],
        center_y_cm=result["center_y_cm"],
        radius_cm=result["radius_cm"],
        waypoints=[PathWaypoint(**w) for w in result["waypoints"]],
        estimated_waypoints=result["estimated_waypoints"],
        estimated_drawing_time_sec=result["estimated_drawing_time_sec"],
        original_png_data_url=_bgr_to_data_url(result.get("original_bgr")),
        traced_png_data_url=_bgr_to_data_url(result.get("traced_bgr")),
    )


def _bgr_to_data_url(bgr) -> Optional[str]:
    """Encode an OpenCV BGR ndarray as a JPEG data URL, or None on failure."""
    if bgr is None:
        return None
    try:
        import cv2
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as exc:
        log.warning("Failed to encode preview image: %s", exc)
        return None
