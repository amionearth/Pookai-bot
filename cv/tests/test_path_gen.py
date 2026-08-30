"""Tests for path_gen.py — no hardware required."""
import math
import numpy as np
import cv2
import pytest

from cv.path_gen   import generate_path, validate_path, PathGenConfig
from cv.models     import CircleResult, SymmetryResult, Waypoint, PathPlan


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_circle_binary(h=400, w=400, cx=200, cy=200, r=150) -> np.ndarray:
    """Binary image with a filled circle — gives plenty of contours."""
    img = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(img, (cx, cy), r - 10, 255, 4)
    # Add some inner rings so there's more to draw
    cv2.circle(img, (cx, cy), r // 2, 255, 3)
    cv2.circle(img, (cx, cy), r // 4, 255, 2)
    return img


_DEFAULT_CIRCLE   = CircleResult(center_x=200, center_y=200, radius=150, confidence=0.9)
_DEFAULT_SYMMETRY = SymmetryResult(order=8, confidence=0.8, angular_period_rad=math.pi / 4)


# ── generate_path ─────────────────────────────────────────────────────────────

def test_generates_waypoints():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    assert len(plan.waypoints) > 0


def test_plan_metadata():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    assert plan.center_x == 200
    assert plan.center_y == 200
    assert plan.symmetry_order == 8


def test_waypoints_theta_in_range():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    for w in plan.waypoints:
        assert 0.0 <= w.theta < 2 * math.pi, f"theta out of range: {w.theta}"


def test_waypoints_r_in_range():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    for w in plan.waypoints:
        assert 0.0 <= w.r <= 1.0, f"r out of range: {w.r}"


def test_pen_states_valid():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    for w in plan.waypoints:
        assert w.pen in (0, 1), f"invalid pen state: {w.pen}"


def test_empty_image_raises():
    blank = np.zeros((400, 400), dtype=np.uint8)
    with pytest.raises(RuntimeError, match="No drawable contours"):
        generate_path(blank, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)


def test_max_waypoints_cap():
    binary = _make_circle_binary()
    cfg    = PathGenConfig(max_waypoints=50)
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY, cfg)
    assert len(plan.waypoints) <= 50


# ── validate_path ─────────────────────────────────────────────────────────────

def test_valid_plan_passes():
    waypoints = [
        Waypoint(theta=0.0,  r=0.5, pen=1),
        Waypoint(theta=0.1,  r=0.5, pen=1),
        Waypoint(theta=0.2,  r=0.5, pen=1),
    ]
    plan   = PathPlan(waypoints=waypoints, center_x=200, center_y=200,
                      radius_px=150, symmetry_order=8)
    result = validate_path(plan)
    assert result.valid


def test_bad_theta_fails():
    waypoints = [
        Waypoint(theta=-0.1, r=0.5, pen=1),
        Waypoint(theta=0.1,  r=0.5, pen=1),
        Waypoint(theta=0.2,  r=0.5, pen=1),
    ]
    plan   = PathPlan(waypoints=waypoints, center_x=200, center_y=200,
                      radius_px=150, symmetry_order=8)
    result = validate_path(plan)
    assert not result.valid
    assert any("theta" in e.message for e in result.errors)


def test_bad_r_fails():
    waypoints = [
        Waypoint(theta=0.0, r=1.5, pen=1),  # r > 1
        Waypoint(theta=0.1, r=0.5, pen=1),
        Waypoint(theta=0.2, r=0.5, pen=1),
    ]
    plan   = PathPlan(waypoints=waypoints, center_x=200, center_y=200,
                      radius_px=150, symmetry_order=8)
    result = validate_path(plan)
    assert not result.valid


def test_nan_r_fails():
    waypoints = [
        Waypoint(theta=0.0,         r=float("nan"), pen=1),
        Waypoint(theta=0.1,         r=0.5,          pen=1),
        Waypoint(theta=0.2,         r=0.5,          pen=1),
    ]
    plan   = PathPlan(waypoints=waypoints, center_x=200, center_y=200,
                      radius_px=150, symmetry_order=8)
    result = validate_path(plan)
    assert not result.valid


def test_invalid_pen_fails():
    waypoints = [
        Waypoint(theta=0.0, r=0.5, pen=2),  # pen must be 0 or 1
        Waypoint(theta=0.1, r=0.5, pen=1),
        Waypoint(theta=0.2, r=0.5, pen=1),
    ]
    plan   = PathPlan(waypoints=waypoints, center_x=200, center_y=200,
                      radius_px=150, symmetry_order=8)
    result = validate_path(plan)
    assert not result.valid


# ── to_dict ───────────────────────────────────────────────────────────────────

def test_to_dict_structure():
    binary = _make_circle_binary()
    plan   = generate_path(binary, _DEFAULT_CIRCLE, _DEFAULT_SYMMETRY)
    d      = plan.to_dict()
    assert d["version"] == 1
    assert "waypoints" in d
    assert "coordinate_system" in d
    assert d["coordinate_system"]["theta"] == "radians"
    for wp in d["waypoints"]:
        assert "theta" in wp
        assert "r"     in wp
        assert "pen"   in wp
