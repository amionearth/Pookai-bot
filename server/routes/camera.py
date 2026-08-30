"""
server/routes/camera.py — Optimized, Crash-Resistant Camera Worker & Live Stream.

Fixes for Raspberry Pi 5:
  1. Threaded Singleton CameraWorker (never blocks web loop or crashes V4L2)
  2. Native MJPG hardware capture at 640x480 (near 0% CPU usage)
  3. Real-time ArUco & Checkerboard detection for robot localization & calibration
  4. Visual HUD with status messages ("Looking for Robot Marker / Checkerboard")
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/camera", tags=["camera"])

# Preferred device index
_PREFERRED_INDEX = int(os.environ.get("POOKALBOT_CAMERA_INDEX", "0"))


# ── Threaded Camera Worker (Singleton) ────────────────────────────────────────

class CameraManager:
    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._active_index: Optional[int] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Latest frame buffers
        self._latest_jpeg: bytes = b""
        self._latest_bgr: Optional[np.ndarray] = None
        self._last_frame_time: float = 0.0
        
        # Marker & Localization state
        self.marker_detected: bool = False
        self.marker_id: Optional[int] = None
        self.robot_x: float = 0.0
        self.robot_y: float = 0.0
        self.robot_theta: float = 0.0
        self.checkerboard_detected: bool = False
        
        self.start()

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        indices_to_try = [_PREFERRED_INDEX, 0, 1, 2, 3]
        # Remove duplicates while preserving order
        indices = list(dict.fromkeys(indices_to_try))
        
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY] if hasattr(cv2, "CAP_V4L2") else [cv2.CAP_ANY]

        for idx in indices:
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        # Set hardware MJPEG to minimize CPU usage on Pi 5
                        try:
                            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                        except Exception:
                            pass
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_FPS, 20)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                        ok, test_frame = cap.read()
                        if ok and test_frame is not None and test_frame.size > 0:
                            log.info("Successfully initialized camera on index %d", idx)
                            self._active_index = idx
                            return cap
                    cap.release()
                except Exception:
                    pass
        return None

    def _worker(self):
        log.info("Camera capture worker started.")
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self._cap = self._open_camera()
                if self._cap is None:
                    # Camera offline — generate informative placeholder
                    self._generate_offline_frame("Connecting to camera device...")
                    time.sleep(1.0)
                    continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                log.warning("Camera read dropped frame, retrying...")
                if self._cap:
                    self._cap.release()
                self._cap = None
                time.sleep(0.5)
                continue

            # Process frame: Marker detection + HUD annotations
            annotated_frame = self._process_and_annotate(frame)

            # Compress once for all connected web clients
            ok_enc, buf = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ok_enc:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()
                    self._latest_bgr = frame
                    self._last_frame_time = time.time()

            # Throttle to ~20 FPS so Pi 5 CPU stays completely cool
            time.sleep(0.045)

        if self._cap:
            self._cap.release()
            self._cap = None

    def _process_and_annotate(self, frame: np.ndarray) -> np.ndarray:
        """Detects robot ArUco marker & checkerboard calibration, and adds visual HUD."""
        annotated = frame.copy()
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Detect ArUco Marker
        marker_found = False
        try:
            dict_types = [
                cv2.aruco.DICT_4X4_50,
                cv2.aruco.DICT_4X4_100,
                cv2.aruco.DICT_5X5_50,
                cv2.aruco.DICT_6X6_50,
                cv2.aruco.DICT_APRILTAG_36h11,
            ]
            for dt in dict_types:
                dictionary = cv2.aruco.getPredefinedDictionary(dt)
                if hasattr(cv2.aruco, "ArucoDetector"):
                    detector = cv2.aruco.ArucoDetector(dictionary)
                    corners, ids, _ = detector.detectMarkers(frame)
                else:
                    corners, ids, _ = cv2.aruco.detectMarkers(frame, dictionary)

                if ids is not None and len(ids) > 0:
                    marker_found = True
                    self.marker_detected = True
                    self.marker_id = int(ids[0][0])
                    
                    # Compute center & heading
                    c = corners[0][0]
                    cx = float(np.mean(c[:, 0]))
                    cy = float(np.mean(c[:, 1]))
                    
                    # Convert to cm from image center (assuming ~7.5 px per cm)
                    self.robot_x = (cx - (w / 2)) / 7.5
                    self.robot_y = (cy - (h / 2)) / 7.5
                    
                    # Heading vector from corner 0 to corner 1
                    dx = float(c[1, 0] - c[0, 0])
                    dy = float(c[1, 1] - c[0, 1])
                    self.robot_theta = math.atan2(dy, dx)

                    # Draw marker box & heading
                    cv2.polylines(annotated, [c.astype(np.int32)], True, (0, 255, 0), 2)
                    cv2.circle(annotated, (int(cx), int(cy)), 5, (0, 0, 255), -1)
                    
                    # Draw heading arrow
                    arrow_x = int(cx + math.cos(self.robot_theta) * 35)
                    arrow_y = int(cy + math.sin(self.robot_theta) * 35)
                    cv2.arrowedLine(annotated, (int(cx), int(cy)), (arrow_x, arrow_y), (0, 255, 255), 2, tipLength=0.3)
                    
                    # Marker label
                    cv2.putText(annotated, f"Robot #{self.marker_id} ({self.robot_x:.1f}, {self.robot_y:.1f}cm)",
                                (int(cx) - 40, int(cy) - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
                    break
        except Exception:
            pass

        if not marker_found:
            self.marker_detected = False

        # 2. Check for Calibration Checkerboard (optional)
        try:
            ret, _ = cv2.findChessboardCorners(gray, (7, 7), cv2.CALIB_CB_FAST_CHECK)
            self.checkerboard_detected = bool(ret)
        except Exception:
            self.checkerboard_detected = False

        # 3. Draw HUD Banner
        # Top bar
        cv2.rectangle(annotated, (0, 0), (w, 30), (20, 25, 30), -1)
        
        status_text = f"CAM OK | Robot: {'FOUND' if self.marker_detected else 'LOOKING FOR MARKER'}"
        status_color = (0, 255, 0) if self.marker_detected else (0, 200, 255)
        cv2.putText(annotated, status_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1, cv2.LINE_AA)

        if not self.marker_detected:
            # Prompt user to place robot tag
            cv2.rectangle(annotated, (w // 2 - 160, h - 35), (w // 2 + 160, h - 5), (20, 25, 30), -1)
            cv2.putText(annotated, "Place Robot Tag in View", (w // 2 - 120, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1, cv2.LINE_AA)

        return annotated

    def _generate_offline_frame(self, msg: str):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 35, 45)
        cv2.putText(img, "POOKALBOT OVERHEAD CAMERA", (140, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2, cv2.LINE_AA)
        cv2.putText(img, msg, (160, 260),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        ok_enc, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ok_enc:
            with self._lock:
                self._latest_jpeg = buf.tobytes()

    def get_latest_jpeg(self) -> bytes:
        with self._lock:
            return self._latest_jpeg

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)


# Instantiate single global manager
_cam_manager = CameraManager()


# ── Routes ────────────────────────────────────────────────────────────────────

def _mjpeg_stream_generator() -> Iterator[bytes]:
    """Efficiently streams frames from the camera manager to web clients."""
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    while True:
        jpeg = _cam_manager.get_latest_jpeg()
        if jpeg:
            yield boundary + jpeg + b"\r\n"
        time.sleep(0.045)  # ~22 FPS


@router.get("/stream", summary="Live MJPEG stream from the overhead camera")
def stream():
    """Returns a continuous lightweight MJPEG stream (640x480, ~20 FPS)."""
    return StreamingResponse(
        _mjpeg_stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/status", summary="Camera & localization status")
def camera_status():
    return {
        "available": _cam_manager._cap is not None and _cam_manager._cap.isOpened(),
        "active_index": _cam_manager._active_index,
        "marker_detected": _cam_manager.marker_detected,
        "marker_id": _cam_manager.marker_id,
        "robot_x": _cam_manager.robot_x,
        "robot_y": _cam_manager.robot_y,
        "robot_theta": _cam_manager.robot_theta,
        "checkerboard_detected": _cam_manager.checkerboard_detected,
    }
