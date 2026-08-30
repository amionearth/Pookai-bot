"""
control/status_reporter.py — Pushes status updates to the web server.
"""
import requests

from . import config


def push(phase, pose=None, progress=None, pen=None, calibrated=None, extra=None):
    payload = {"phase": phase}
    if pose is not None:
        payload["x_cm"] = float(pose[0])
        payload["y_cm"] = float(pose[1])
        payload["heading_rad"] = float(pose[2])
    if progress is not None:
        payload["progress"] = float(progress)
    if pen is not None:
        payload["pen"] = bool(pen)
    if calibrated is not None:
        payload["calibrated"] = bool(calibrated)
    if extra:
        payload.update(extra)

    try:
        requests.post(config.PI_STATUS_URL, json=payload, timeout=0.3)
    except Exception:
        pass
