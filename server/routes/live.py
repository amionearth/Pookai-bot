"""
server/routes/live.py — live state for the on-floor overlays.

  GET  /api/live/state             Current state (robot pose, drawing progress, pen)
  POST /api/live/state             The ML/control service POSTs here to push state
  POST /api/live/simulate/start    Start a fake drawing session (for demos)
  POST /api/live/simulate/stop     Stop any running simulation

The web app's live-view canvas polls /api/live/state ~5×/sec and draws the
overlays accordingly. The ML/control service should POST at ~10 Hz.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live"])


# ── State model ─────────────────────────────────────────────────────────────

class RobotPose(BaseModel):
    x:          float = 0.0          # cm, world frame (centred on the design)
    y:          float = 0.0
    theta:      float = 0.0          # radians, 0 = +x
    detected:   bool  = False        # True if ArUco is currently seen
    marker_id:  Optional[int] = None
    confidence: float = 0.0


class DrawingProgress(BaseModel):
    current_waypoint: int = 0
    total_waypoints:   int = 0
    drawing:           bool = False
    state:             Literal["idle", "starting", "drawing", "paused", "done", "error"] = "idle"
    eta_seconds:       int = 0


class LiveState(BaseModel):
    timestamp_ms: int = 0
    robot:        RobotPose       = Field(default_factory=RobotPose)
    progress:     DrawingProgress = Field(default_factory=DrawingProgress)
    pen:          Literal["up", "down"] = "up"
    message:      Optional[str] = None
    control_service_connected: bool = False


# ── In-memory state ─────────────────────────────────────────────────────────

_state = LiveState(timestamp_ms=int(time.time() * 1000))
_simulation_task: Optional[asyncio.Task] = None
_waypoints: List[dict] = []


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/state", response_model=LiveState, summary="Get current live state")
async def get_state() -> LiveState:
    """Frontend polls this ~5 times per second."""
    _state.timestamp_ms = int(time.time() * 1000)
    
    # Lazy import to avoid circular dependencies
    from server.routes.camera import _cam_manager
    
    # If not running virtual demo simulator, feed live camera ArUco detection
    if not (_simulation_task and not _simulation_task.done()):
        if _cam_manager.marker_detected:
            _state.robot.detected = True
            _state.robot.marker_id = _cam_manager.marker_id
            _state.robot.x = _cam_manager.robot_x
            _state.robot.y = _cam_manager.robot_y
            _state.robot.theta = _cam_manager.robot_theta
            _state.robot.confidence = 0.98
            _state.message = f"Robot #{_cam_manager.marker_id} tracked at ({_cam_manager.robot_x:.1f}, {_cam_manager.robot_y:.1f}) cm"
        else:
            _state.robot.detected = False
            if not _state.message:
                _state.message = "Looking for Robot Marker / Checkerboard on floor…"
            
    return _state


@router.post("/state", response_model=LiveState, summary="Push state from the control service")
async def push_state(state: LiveState) -> LiveState:
    """The ML/control service calls this to publish its current state."""
    global _state
    _state = state
    _state.control_service_connected = True
    _state.timestamp_ms = int(time.time() * 1000)
    return _state


# ── Demo simulator ──────────────────────────────────────────────────────────
#
# Lets you see the full live-view experience in action even before the
# localization + control service is wired up. Walks the robot through the
# traced waypoints, updates the state as if a real robot were running.

@router.post("/simulate/start", summary="Start a fake drawing session (for demos)")
async def simulate_start(waypoints: List[dict], speed_wps: int = 40) -> dict:
    """
    Start a fake drawing session that walks the simulated robot through the
    given waypoints. Useful for demoing the live overlay without hardware.

    Parameters
    ----------
    waypoints : list of {x, y, pen} dicts (the same shape as vectorize output)
    speed_wps : simulated waypoints per second (default 40 = matches the
                drawing-speed estimate used by vectorize)
    """
    global _simulation_task, _waypoints
    if not waypoints:
        return {"ok": False, "error": "no waypoints provided"}
    _waypoints = waypoints
    if _simulation_task and not _simulation_task.done():
        _simulation_task.cancel()
    _simulation_task = asyncio.create_task(_simulate(speed_wps))
    return {"ok": True, "waypoints": len(waypoints), "speed_wps": speed_wps}


@router.post("/simulate/stop", summary="Stop any running simulation")
async def simulate_stop() -> dict:
    global _simulation_task, _state
    if _simulation_task and not _simulation_task.done():
        _simulation_task.cancel()
        _simulation_task = None
    _state.progress.state = "idle"
    _state.progress.drawing = False
    _state.progress.current_waypoint = 0
    _state.pen = "up"
    return {"ok": True}


# ── Simulator implementation ────────────────────────────────────────────────

async def _simulate(speed_wps: int) -> None:
    global _state
    total = len(_waypoints)
    if total == 0:
        return

    # Reset
    _state.progress.total_waypoints = total
    _state.progress.current_waypoint = 0
    _state.progress.state = "starting"
    _state.progress.drawing = False
    _state.progress.eta_seconds = total // max(speed_wps, 1)
    _state.robot.detected = True
    _state.robot.marker_id = 0
    _state.robot.confidence = 0.95
    first = _waypoints[0]
    _state.robot.x = first["x"]
    _state.robot.y = first["y"]
    _state.robot.theta = 0.0
    _state.pen = "up"
    _state.message = "Waking up the robot…"
    _state.timestamp_ms = int(time.time() * 1000)

    await asyncio.sleep(0.5)

    # Walk through
    _state.progress.state = "drawing"
    _state.progress.drawing = True
    _state.message = None

    dt = 1.0 / max(speed_wps, 1)
    for i, wp in enumerate(_waypoints):
        _state.progress.current_waypoint = i + 1
        _state.progress.eta_seconds = max(0, int((total - i - 1) * dt))
        _state.pen = "down" if wp.get("pen") == 1 else "up"
        _state.robot.x = wp["x"]
        _state.robot.y = wp["y"]
        if i > 0:
            prev = _waypoints[i - 1]
            _state.robot.theta = math.atan2(
                wp["y"] - prev["y"],
                wp["x"] - prev["x"],
            )
        _state.timestamp_ms = int(time.time() * 1000)
        await asyncio.sleep(dt)

    # Done
    _state.progress.state = "done"
    _state.progress.drawing = False
    _state.progress.eta_seconds = 0
    _state.pen = "up"
    _state.message = "Drawing complete."
    _state.timestamp_ms = int(time.time() * 1000)
    log.info("Simulation complete: %d waypoints", total)
