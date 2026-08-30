"""Tests for circle_detect.py — uses synthetic images, no hardware."""
import numpy as np
import cv2
import pytest

from cv.circle_detect import detect_circle, draw_circle_debug, CircleDetectConfig
from cv.models import CircleResult


def _synthetic_circle_image(
    h: int = 400, w: int = 400,
    cx: int = 200, cy: int = 200, r: int = 150,
    noise: bool = False,
) -> np.ndarray:
    """White circle ring on dark background — easy for HoughCircles."""
    img = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(img, (cx, cy), r, 255, 3)
    if noise:
        rng = np.random.default_rng(42)
        img = np.clip(img + rng.integers(0, 30, img.shape, dtype=np.uint8), 0, 255).astype(np.uint8)
    return img


# ── Basic detection ───────────────────────────────────────────────────────────

def test_detects_synthetic_circle():
    gray = _synthetic_circle_image()
    cfg  = CircleDetectConfig(param2=15, blur_before=3)
    result = detect_circle(gray, cfg)
    assert abs(result.center_x - 200) < 15
    assert abs(result.center_y - 200) < 15
    assert abs(result.radius   - 150) < 20


def test_confidence_is_reasonable():
    gray   = _synthetic_circle_image()
    cfg    = CircleDetectConfig(param2=15, blur_before=3)
    result = detect_circle(gray, cfg)
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence > 0.3


# ── No-detection case ────────────────────────────────────────────────────────

def test_blank_image_raises():
    gray = np.zeros((400, 400), dtype=np.uint8)
    with pytest.raises(RuntimeError):
        detect_circle(gray)


# ── Debug image ───────────────────────────────────────────────────────────────

def test_draw_circle_debug_shape():
    h, w = 400, 400
    bgr = np.zeros((h, w, 3), dtype=np.uint8)
    result = CircleResult(center_x=200, center_y=200, radius=150, confidence=0.9)
    out = draw_circle_debug(bgr, result)
    assert out.shape == bgr.shape
