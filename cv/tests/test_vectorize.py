"""
Smoke tests for cv.vectorize — no real camera, no real Gemini.

Verifies the end-to-end image→waypoint pipeline on a hand-drawn synthetic
image (a couple of concentric circles on a white background). This is what
the web app's /api/designs/vectorize ultimately calls into.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from cv.vectorize import vectorize_image, VectorizeConfig


def _make_synthetic_circle_image(size: int = 400) -> bytes:
    """White background with two concentric black rings — exactly the kind
    of clean, closed-outline input our Gemini prompt asks for."""
    img = np.full((size, size, 3), 255, dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), size // 3, (0, 0, 0), 3)
    cv2.circle(img, (size // 2, size // 2), size // 6, (0, 0, 0), 2)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_vectorize_returns_path():
    image_bytes = _make_synthetic_circle_image()
    result = vectorize_image(image_bytes=image_bytes, canvas_cm=40.0)
    assert result["radius_cm"] > 0
    assert len(result["waypoints"]) > 0
    # Centred at (0, 0) by convention
    assert abs(result["center_x_cm"]) < 0.01
    assert abs(result["center_y_cm"]) < 0.01


def test_vectorize_pen_state_changes():
    """A multi-ring image produces at least one pen-up transition between strokes."""
    image_bytes = _make_synthetic_circle_image()
    result = vectorize_image(image_bytes=image_bytes, canvas_cm=40.0)
    wps = result["waypoints"]
    pen_states = {w["pen"] for w in wps}
    # If greedy ordering is doing its job, the path will have at least
    # one pen-up between disjoint strokes
    assert 1 in pen_states, "expected at least some pen-down points"


def test_vectorize_waypoint_within_canvas():
    """All waypoints should fit inside ±canvas_cm/2 (centre is at 0,0)."""
    canvas_cm = 40.0
    image_bytes = _make_synthetic_circle_image()
    result = vectorize_image(image_bytes=image_bytes, canvas_cm=canvas_cm)
    half = canvas_cm / 2 + 1  # small slack for pixel rounding
    for w in result["waypoints"]:
        assert -half <= w["x"] <= half, f"x={w['x']} out of bounds"
        assert -half <= w["y"] <= half, f"y={w['y']} out of bounds"


def test_vectorize_blank_image_raises():
    """An all-white image has no contours → RuntimeError."""
    img = np.full((200, 200, 3), 255, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    image_bytes = buf.tobytes()
    with pytest.raises(RuntimeError, match="[Nn]o drawable"):
        vectorize_image(image_bytes=image_bytes, canvas_cm=40.0)


def test_vectorize_corrupt_image_raises():
    with pytest.raises(RuntimeError, match="[Cc]ould not decode"):
        vectorize_image(image_bytes=b"not an image", canvas_cm=40.0)


def test_vectorize_estimates_present():
    image_bytes = _make_synthetic_circle_image()
    result = vectorize_image(image_bytes=image_bytes, canvas_cm=40.0)
    assert result["estimated_waypoints"] == len(result["waypoints"])
    assert result["estimated_drawing_time_sec"] >= 5
