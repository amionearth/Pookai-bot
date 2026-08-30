"""
control/calibration.py — Checkerboard camera-to-floor homography calibration.
"""
import json
import os
import time

import cv2
import numpy as np

from . import config


def _object_points():
    cols, rows = config.CHECKERBOARD_INNER_CORNERS
    objp = np.zeros((rows * cols, 2), dtype=np.float32)
    grid = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp[:, :2] = grid * config.CHECKERBOARD_SQUARE_CM
    return objp


def find_checkerboard(frame_bgr):
    """Returns (found: bool, corners_px: np.ndarray|None, annotated_frame)."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(
        gray, config.CHECKERBOARD_INNER_CORNERS,
        flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
    )
    annotated = frame_bgr.copy()
    if found:
        corners = cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )
        cv2.drawChessboardCorners(annotated, config.CHECKERBOARD_INNER_CORNERS, corners, found)
    return found, (corners if found else None), annotated


def compute_and_save(corners_px):
    obj_pts = _object_points()
    img_pts = corners_px.reshape(-1, 2).astype(np.float32)

    H, mask = cv2.findHomography(img_pts, obj_pts, method=0)
    if H is None:
        raise RuntimeError("findHomography failed despite detected corners — try recapturing")

    payload = {
        "homography": H.tolist(),
        "calibrated_at": time.time(),
        "checkerboard_inner_corners": list(config.CHECKERBOARD_INNER_CORNERS),
        "checkerboard_square_cm": config.CHECKERBOARD_SQUARE_CM,
    }
    with open(config.CALIBRATION_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    return H


def load_homography():
    if not os.path.exists(config.CALIBRATION_FILE):
        return None
    try:
        with open(config.CALIBRATION_FILE) as f:
            payload = json.load(f)
        return np.array(payload["homography"], dtype=np.float64)
    except Exception:
        return None


def status():
    if not os.path.exists(config.CALIBRATION_FILE):
        return {
            "calibrated": False,
            "message": "No calibration on file — place checkerboard in camera view and click Calibrate Floor."
        }
    try:
        with open(config.CALIBRATION_FILE) as f:
            payload = json.load(f)
        age_s = time.time() - payload.get("calibrated_at", time.time())
        return {
            "calibrated": True,
            "calibrated_seconds_ago": round(age_s, 1),
            "checkerboard_inner_corners": payload.get("checkerboard_inner_corners", [9, 6]),
            "checkerboard_square_cm": payload.get("checkerboard_square_cm", 2.5),
            "message": f"Calibrated {round(age_s/60, 1)}m ago ({payload.get('checkerboard_square_cm', 2.5)}cm squares)"
        }
    except Exception:
        return {"calibrated": False, "message": "Corrupted calibration file."}


def pixel_to_cm(homography, pixel_xy):
    """Apply the homography to (px, py) -> (cm_x, cm_y)."""
    pt = np.array([[pixel_xy]], dtype=np.float32)
    out = cv2.perspectiveTransform(pt, homography.astype(np.float32))
    return float(out[0, 0, 0]), float(out[0, 0, 1])
