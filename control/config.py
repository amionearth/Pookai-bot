"""
control/config.py — Control and Vision configuration parameters for PookalBot.
"""
import os
from pathlib import Path

# ── Network ──────────────────────────────────────────────────────────────
ESP32_IP = os.environ.get("POOKALBOT_ESP32_IP", "192.168.11.237")
ESP32_PORT = int(os.environ.get("POOKALBOT_ESP32_PORT", "9000"))

PI_STATUS_URL = os.environ.get(
    "POOKALBOT_STATUS_URL", "http://127.0.0.1:8000/api/live/state"
)

CONTROL_HOST = os.environ.get("POOKALBOT_CONTROL_HOST", "0.0.0.0")
CONTROL_PORT = int(os.environ.get("POOKALBOT_CONTROL_PORT", "9100"))

# ── Camera ───────────────────────────────────────────────────────────────
CAMERA_INDEX = int(os.environ.get("POOKALBOT_CAMERA_INDEX", "0"))

# ── Checkerboard calibration ────────────────────────────────────────────
# 9x6 inner corners (10x7 squares)
CHECKERBOARD_INNER_CORNERS = (9, 6)
CHECKERBOARD_SQUARE_CM = float(os.environ.get("POOKALBOT_CHECKERBOARD_SQUARE_CM", "2.5"))
CALIBRATION_FILE = str(Path(__file__).resolve().parent / "calibration.json")

# ── ArUco Marker ────────────────────────────────────────────────────────
ARUCO_DICT = "DICT_4X4_50"
ARUCO_MARKER_ID = int(os.environ.get("POOKALBOT_ARUCO_ID", "0"))

# ── Mouse odometry ───────────────────────────────────────────────────────
MOUSE_COUNTS_PER_CM = float(os.environ.get("POOKALBOT_MOUSE_COUNTS_PER_CM", "40.0"))
MOUSE_DEVICE_PATH = os.environ.get("POOKALBOT_MOUSE_DEVICE", "")

# ── Robot physical constants ────────────────────────────────────────────
WHEELBASE_CM = float(os.environ.get("POOKALBOT_WHEELBASE_CM", "12.0"))
MAX_PWM = int(os.environ.get("POOKALBOT_MAX_PWM", "200"))
MIN_PWM_TO_MOVE = int(os.environ.get("POOKALBOT_MIN_PWM", "90"))

# ── Control loop tuning ─────────────────────────────────────────────────
LOOP_HZ = 10
WAYPOINT_REACHED_CM = float(os.environ.get("POOKALBOT_WAYPOINT_REACHED_CM", "1.5"))
HEADING_KP = float(os.environ.get("POOKALBOT_HEADING_KP", "90.0"))
CAMERA_STALE_AFTER_S = 1.0
ODOMETRY_ONLY_TIMEOUT_S = 4.0
