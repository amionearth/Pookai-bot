"""
control/server.py — Autonomous Execution & Localization Service (Port 9100).
"""
import logging
import threading
import time
from typing import List, Optional

import cv2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import calibration, config, esp32_link, localization, status_reporter
from .controller import WaypointFollower

log = logging.getLogger(__name__)

app = FastAPI(title="PookalBot Autonomous Control Service")

_state_lock = threading.Lock()
_state = {
    "phase": "idle",
    "pose": None,
    "progress": 0.0,
    "current_waypoint": 0,
    "total_waypoints": 0,
    "pen": False,
    "message": "",
}
_job_thread = None
_stop_requested = threading.Event()


def _set_state(**kwargs):
    with _state_lock:
        _state.update(kwargs)


class Waypoint(BaseModel):
    x: float
    y: float
    pen: int = 0


class DrawRequest(BaseModel):
    design_id: Optional[str] = None
    canvas_cm: float = 60.0
    waypoints: List[Waypoint]


@app.post("/calibration/capture")
def calibration_capture():
    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    try:
        if not cam.isOpened():
            raise HTTPException(503, f"Can't open camera index {config.CAMERA_INDEX}")
        ok, frame = cam.read()
        if not ok:
            raise HTTPException(503, "Camera opened but returned no frame")

        found, corners, annotated = calibration.find_checkerboard(frame)
        if not found:
            return {
                "success": False,
                "message": (
                    "No checkerboard detected. Ensure the 9x6 inner corner (10x7 square) board "
                    "is flat, well-lit, and in full view of the camera."
                ),
            }

        calibration.compute_and_save(corners)
        return {"success": True, "message": "Checkerboard calibration saved successfully.", "status": calibration.status()}
    finally:
        cam.release()


@app.get("/calibration/status")
def calibration_status():
    return calibration.status()


@app.post("/draw")
def draw(req: DrawRequest):
    global _job_thread

    with _state_lock:
        if _state["phase"] == "drawing":
            raise HTTPException(409, "Already drawing — stop or wait for job to finish.")

    _stop_requested.clear()
    wps = [w.model_dump() for w in req.waypoints]
    _job_thread = threading.Thread(target=_run_job, args=(wps,), daemon=True)
    _job_thread.start()
    return {"accepted": True, "waypoint_count": len(wps)}


@app.post("/estop")
def estop():
    _stop_requested.set()
    return {"stopping": True}


@app.get("/status")
def status():
    with _state_lock:
        return dict(_state)


def _run_job(waypoints):
    total = len(waypoints)
    _set_state(phase="drawing", progress=0.0, current_waypoint=0, total_waypoints=total, message="Drawing initiated.")
    status_reporter.push(phase="drawing", progress=0.0, calibrated=True)

    locator = localization.ArucoLocator()
    odometer = localization.MouseOdometer()
    fusion = localization.PoseFusion()
    follower = WaypointFollower(waypoints)
    link = esp32_link.Esp32Link()

    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    period = 1.0 / config.LOOP_HZ

    try:
        if not cam.isOpened():
            _set_state(phase="error", message=f"Can't open camera index {config.CAMERA_INDEX}")
            return

        while not follower.done and not _stop_requested.is_set():
            tick_start = time.time()

            ok, frame = cam.read()
            det = locator.detect(frame) if ok else None
            camera_pose = (det[0], det[1], det[2]) if det else None

            dx_cm, dy_cm = odometer.poll_cm()
            pose = fusion.update(camera_pose, dx_cm, dy_cm)

            stale_for = fusion.seconds_since_camera_fix()
            if stale_for > config.ODOMETRY_ONLY_TIMEOUT_S:
                link.stop()
                _set_state(
                    phase="error",
                    message=f"Lost the marker for {stale_for:.1f}s — stopped for safety. Ensure robot marker is visible.",
                )
                status_reporter.push(phase="error", pose=pose)
                return

            left, right, pen = follower.step(pose)
            link.send(left, right, pen)

            _set_state(
                phase="drawing",
                pose=pose,
                progress=follower.progress,
                current_waypoint=follower.index,
                total_waypoints=total,
                pen=bool(pen),
            )
            status_reporter.push(phase="drawing", pose=pose, progress=follower.progress, pen=pen)

            elapsed = time.time() - tick_start
            time.sleep(max(0.0, period - elapsed))

        link.stop()
        if _stop_requested.is_set():
            _set_state(phase="estopped", message="Stopped by user request.")
            status_reporter.push(phase="estopped")
        else:
            _set_state(phase="idle", progress=1.0, current_waypoint=total, total_waypoints=total, message="Drawing complete! Happy Onam!")
            status_reporter.push(phase="idle", progress=1.0)

    finally:
        cam.release()
        link.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.CONTROL_HOST, port=config.CONTROL_PORT)
