"""
server/routes/calibration.py — Camera-to-Floor Checkerboard Homography Calibration.
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2
from fastapi import APIRouter, HTTPException

import control.calibration as calib_module
from server.routes.camera import CameraManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.post("/capture", summary="Capture checkerboard and calibrate camera-to-floor homography")
def capture_calibration():
    """Finds checkerboard corners in current camera frame and calculates homography."""
    cam_mgr = CameraManager.get_instance()
    frame = cam_mgr.get_latest_frame()
    
    if frame is None:
        raise HTTPException(status_code=503, detail="Camera frame not available. Ensure overhead camera is connected.")

    found, corners, annotated = calib_module.find_checkerboard(frame)
    if not found:
        return {
            "success": False,
            "calibrated": False,
            "message": (
                "⚠ Checkerboard not detected. Ensure the 9x6 inner corners (10x7 squares) board "
                "is lying completely flat on the floor in clear view of the camera."
            ),
        }

    try:
        H = calib_module.compute_and_save(corners)
        stat = calib_module.status()
        return {
            "success": True,
            "calibrated": True,
            "message": f"✓ Floor calibrated successfully ({stat.get('checkerboard_square_cm', 2.5)}cm squares). Ready to draw!",
            "status": stat,
        }
    except Exception as exc:
        log.exception("Calibration computation failed")
        raise HTTPException(status_code=500, detail=f"Calibration math error: {exc}")


@router.get("/status", summary="Get checkerboard calibration status")
def get_calibration_status():
    return calib_module.status()
