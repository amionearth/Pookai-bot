"""
server/routes/paths.py — /api/path/* endpoints (stub for next stage).

TODO: POST /api/path/preview
  1. Fetch selected SVG from designs state
  2. Parse SVG paths → Cartesian XY points
  3. Run cv.path_gen.generate_path() → PathPlan
  4. Return theta/r/pen waypoints as JSON
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/path", tags=["path"])


@router.get("/preview", summary="Path preview (not yet implemented)")
async def path_preview():
    """
    Placeholder — SVG → polar waypoints conversion.
    Will be implemented in the next stage using the existing cv/ pipeline.
    """
    return {
        "status": "not_implemented",
        "message": "Path preview will be connected in the next stage.",
        "next_steps": [
            "Parse selected SVG into XY contours",
            "Run cv.path_gen.generate_path()",
            "Return theta/r/pen_state waypoints",
        ],
    }
