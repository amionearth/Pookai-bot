"""
control/localization.py — ArUco tracking, floor coordinate transformation, and sensor fusion.
"""
import math
import time

import cv2
import numpy as np

from . import calibration, config

try:
    from evdev import InputDevice, ecodes, list_devices
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False


class ArucoLocator:
    """Detects the robot marker each frame and converts it to (x_cm, y_cm, heading_rad)."""

    def __init__(self):
        self.homography = calibration.load_homography()
        
        # Support multiple ArUco dictionaries for maximum compatibility
        self.dictionaries = []
        for dname in ["DICT_4X4_50", "DICT_4X4_100", "DICT_5X5_50", "DICT_6X6_50", "DICT_APRILTAG_36h11"]:
            if hasattr(cv2.aruco, dname):
                dict_obj = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dname))
                self.dictionaries.append((dname, dict_obj))

        if hasattr(cv2.aruco, "ArucoDetector"):
            params = cv2.aruco.DetectorParameters()
            params.adaptiveThreshWinSizeMin = 3
            params.adaptiveThreshWinSizeMax = 23
            params.adaptiveThreshWinSizeStep = 10
            self._detectors = [(name, cv2.aruco.ArucoDetector(d, params)) for name, d in self.dictionaries]
            self._legacy = False
        else:
            self._params = cv2.aruco.DetectorParameters_create()
            self._legacy = True

    def reload_calibration(self):
        self.homography = calibration.load_homography()

    def detect(self, frame_bgr):
        """Returns (x_cm, y_cm, heading_rad, marker_id, corners_px) or None."""
        if frame_bgr is None:
            return None

        # 1. Detect markers across dictionaries
        best_corners = None
        best_id = None

        if self._legacy:
            for _, d in self.dictionaries:
                corners, ids, _ = cv2.aruco.detectMarkers(frame_bgr, d, parameters=self._params)
                if ids is not None and len(ids) > 0:
                    best_corners = corners[0].reshape(4, 2)
                    best_id = int(ids.flatten()[0])
                    break
        else:
            for _, det in self._detectors:
                corners, ids, _ = det.detectMarkers(frame_bgr)
                if ids is not None and len(ids) > 0:
                    best_corners = corners[0].reshape(4, 2)
                    best_id = int(ids.flatten()[0])
                    break

        if best_corners is None:
            return None

        center_px = best_corners.mean(axis=0)
        front_vec_px = best_corners[1] - best_corners[0]

        if self.homography is not None:
            cx, cy = calibration.pixel_to_cm(self.homography, tuple(center_px))
            tip_px = center_px + front_vec_px
            tx, ty = calibration.pixel_to_cm(self.homography, tuple(tip_px))
            heading = math.atan2(ty - cy, tx - cx)
            return cx, cy, heading, best_id, best_corners
        else:
            # Fallback coordinate scaling if not calibrated yet
            h, w = frame_bgr.shape[:2]
            cx = (center_px[0] - (w / 2)) * 0.1
            cy = (center_px[1] - (h / 2)) * 0.1
            heading = math.atan2(front_vec_px[1], front_vec_px[0])
            return cx, cy, heading, best_id, best_corners


def find_mouse_device():
    if not _EVDEV_AVAILABLE:
        return None
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities().get(ecodes.EV_REL, [])
            if ecodes.REL_X in caps and ecodes.REL_Y in caps:
                return path
        except Exception:
            pass
    return None


class MouseOdometer:
    """Reads relative motion from optical mouse sensor."""

    def __init__(self, device_path=None):
        self._dx_counts = 0
        self._dy_counts = 0
        self._device = None
        self._available = False

        if not _EVDEV_AVAILABLE:
            return
        path = device_path or config.MOUSE_DEVICE_PATH or find_mouse_device()
        if not path:
            return
        try:
            self._device = InputDevice(path)
            self._device.grab()
            import fcntl, os as _os
            fl = fcntl.fcntl(self._device.fd, fcntl.F_GETFL)
            fcntl.fcntl(self._device.fd, fcntl.F_SETFL, fl | _os.O_NONBLOCK)
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self):
        return self._available

    def _drain_events(self):
        if not self._available or not self._device:
            return
        try:
            for event in self._device.read():
                if event.type == ecodes.EV_REL:
                    if event.code == ecodes.REL_X:
                        self._dx_counts += event.value
                    elif event.code == ecodes.REL_Y:
                        self._dy_counts += event.value
        except Exception:
            pass

    def poll_cm(self):
        self._drain_events()
        dx_cm = self._dx_counts / config.MOUSE_COUNTS_PER_CM
        dy_cm = self._dy_counts / config.MOUSE_COUNTS_PER_CM
        self._dx_counts = 0
        self._dy_counts = 0
        return dx_cm, dy_cm


class PoseFusion:
    """Fuses camera ArUco marker pose and mouse sensor odometry."""

    def __init__(self, x_cm=0.0, y_cm=0.0, heading_rad=0.0):
        self.x = x_cm
        self.y = y_cm
        self.heading = heading_rad
        self.last_camera_fix_time = 0.0
        self.have_ever_seen_camera = False

    def update(self, camera_pose, odom_dx_cm, odom_dy_cm, now=None):
        now = now if now is not None else time.time()

        c, s = math.cos(self.heading), math.sin(self.heading)
        world_dx = odom_dx_cm * c - odom_dy_cm * s
        world_dy = odom_dx_cm * s + odom_dy_cm * c
        self.x += world_dx
        self.y += world_dy

        if camera_pose is not None:
            cam_x, cam_y, cam_heading = camera_pose[:3]
            self.have_ever_seen_camera = True
            self.last_camera_fix_time = now
            
            blend = 0.85
            self.x = blend * cam_x + (1 - blend) * self.x
            self.y = blend * cam_y + (1 - blend) * self.y
            heading_diff = _wrap_angle(cam_heading - self.heading)
            self.heading = _wrap_angle(self.heading + 0.35 * heading_diff)

        return self.x, self.y, self.heading

    def seconds_since_camera_fix(self, now=None):
        now = now if now is not None else time.time()
        if not self.have_ever_seen_camera:
            return float("inf")
        return now - self.last_camera_fix_time


def _wrap_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi
