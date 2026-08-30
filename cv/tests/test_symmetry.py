"""
Tests for symmetry.py — synthetic patterns with known rotational symmetry.
No hardware required.
"""
import math
import numpy as np
import cv2
import pytest

from cv.symmetry import build_polar, detect_symmetry, angular_projection, circular_autocorrelation
from cv.models   import PolarRepresentation


# ── Synthetic Pookalam helpers ────────────────────────────────────────────────

def _make_nfold_image(
    order: int,
    h: int = 512, w: int = 512,
    r: int = 200,
) -> np.ndarray:
    """
    Draw *order* radial lines/petals on a dark background.
    The resulting angular signal has clear *order*-fold symmetry.
    """
    cx, cy = w // 2, h // 2
    img = np.zeros((h, w), dtype=np.uint8)
    for k in range(order):
        angle = 2 * math.pi * k / order
        ex = int(cx + r * math.cos(angle))
        ey = int(cy + r * math.sin(angle))
        cv2.line(img, (cx, cy), (ex, ey), 255, 4)
    return img


def _polar_from_image(img: np.ndarray, order: int) -> PolarRepresentation:
    h, w = img.shape[:2]
    return build_polar(img, cx=w / 2, cy=h / 2, radius_px=200, theta_bins=720, r_bins=256)


# ── Autocorrelation sanity ────────────────────────────────────────────────────

def test_acf_zero_lag_is_one():
    signal = np.random.randn(360)
    acf = circular_autocorrelation(signal)
    assert abs(acf[0] - 1.0) < 1e-9


def test_acf_periodic_signal():
    """A purely periodic signal should have high ACF at its period."""
    period = 45   # 45-bin period → 8-fold in 360 bins
    t      = np.arange(360)
    signal = np.sin(2 * np.pi * t / period)
    acf    = circular_autocorrelation(signal)
    # ACF should peak at the period lag
    assert acf[period] > 0.8


# ── Angular projection ────────────────────────────────────────────────────────

def test_angular_projection_shape():
    polar_img = np.random.randint(0, 255, (256, 720), dtype=np.uint8)
    proj = angular_projection(polar_img)
    assert proj.shape == (720,)


# ── Symmetry detection with known orders ─────────────────────────────────────

@pytest.mark.parametrize("order", [4, 6, 8, 12])
def test_detects_nfold_symmetry(order: int):
    img   = _make_nfold_image(order)
    polar = _polar_from_image(img, order)
    result = detect_symmetry(polar)
    # Allow ±1 order tolerance for quantisation effects
    assert abs(result.order - order) <= 1, (
        f"Expected ~{order}-fold, got {result.order}"
    )
    assert 0.0 <= result.confidence <= 1.0


def test_symmetry_result_fields():
    img   = _make_nfold_image(8)
    polar = _polar_from_image(img, 8)
    result = detect_symmetry(polar)
    assert result.angular_period_rad == pytest.approx(2 * math.pi / result.order, rel=1e-5)
