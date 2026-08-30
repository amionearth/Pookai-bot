"""Tests for polar coordinate conversion — numerical accuracy."""
import math
import numpy as np
import pytest

from cv.path_gen import _cartesian_to_polar_norm


# ── Cartesian → polar ─────────────────────────────────────────────────────────

def test_origin_point():
    # Point at centre → r should be 0
    pts    = np.array([[100, 100]])  # cx=cy=100
    result = _cartesian_to_polar_norm(pts, cx=100, cy=100, radius_px=50)
    theta, r = result[0]
    assert r == pytest.approx(0.0, abs=1e-6)


def test_right_axis():
    # Point directly to the right of centre
    pts    = np.array([[150, 100]])  # cx=100, cy=100, dx=50, dy=0
    result = _cartesian_to_polar_norm(pts, cx=100, cy=100, radius_px=50)
    theta, r = result[0]
    assert r     == pytest.approx(1.0, abs=1e-6)
    assert theta == pytest.approx(0.0, abs=1e-6)


def test_top_axis():
    # Point directly above (dy = -50 in image coords)
    pts    = np.array([[100, 50]])   # cx=100, cy=100, dx=0, dy=-50
    result = _cartesian_to_polar_norm(pts, cx=100, cy=100, radius_px=50)
    theta, r = result[0]
    assert r == pytest.approx(1.0, abs=1e-6)
    # atan2(-50, 0) = -π/2 → wrapped to 3π/2
    assert theta == pytest.approx(3 * math.pi / 2, abs=1e-6)


def test_theta_always_non_negative():
    pts = np.array([
        [50,  100],  # left
        [100, 150],  # below
        [150, 100],  # right
        [100, 50],   # above
    ])
    result = _cartesian_to_polar_norm(pts, cx=100, cy=100, radius_px=50)
    for theta, r in result:
        assert theta >= 0.0
        assert theta <  2 * math.pi


def test_r_clamped_to_one():
    # Point outside the circle should clamp to 1
    pts    = np.array([[300, 100]])  # far right, radius_px=50
    result = _cartesian_to_polar_norm(pts, cx=100, cy=100, radius_px=50)
    _, r = result[0]
    assert r <= 1.0


def test_multiple_points_accuracy():
    # Quarter-circle at distance 0.5 * radius
    angles   = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
    radius   = 100.0
    half_r   = radius / 2
    pts      = np.array([
        [200 + half_r * math.cos(a), 200 + half_r * math.sin(a)]
        for a in angles
    ])
    result = _cartesian_to_polar_norm(pts.astype(int), cx=200, cy=200, radius_px=radius)
    for i, (theta, r) in enumerate(result):
        expected_theta = angles[i] % (2 * math.pi)
        assert r     == pytest.approx(0.5, abs=0.02)
        assert theta == pytest.approx(expected_theta, abs=0.05)
