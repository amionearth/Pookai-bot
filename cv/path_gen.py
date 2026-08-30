"""
path_gen.py — convert a preprocessed Pookalam image into polar-plotter waypoints.

Pipeline
--------
1. Extract contours from the binary image (inside the detected circle).
2. Order each contour for minimal travel distance (greedy nearest-neighbour).
3. Convert Cartesian contour points → normalised polar (theta, r).
4. Simplify with Ramer–Douglas–Peucker.
5. Apply minimum-distance filter to drop redundant points.
6. Insert pen-up transitions between disjoint segments.
7. Validate the final waypoint list.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Optional
import cv2
import numpy as np

from .models import (
    CircleResult, PathPlan, SymmetryResult,
    Waypoint, ValidationResult, ValidationError,
)


# ── Configuration ─────────────────────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class PathGenConfig:
    rdp_epsilon: float = 1.5       # RDP simplification tolerance (pixels)
    min_segment_px: float = 4.0    # drop points closer than this (pixels)
    min_contour_area: float = 20.0 # ignore tiny noise contours
    pen_up_theta_jump: float = 0.3 # rad gap that triggers a pen-up transition
    pen_up_r_jump: float = 0.15    # normalised-r gap that triggers pen-up
    max_waypoints: int = 2000      # hard cap — reduce rdp_epsilon if hit


# ── Contour extraction ────────────────────────────────────────────────────────

def _mask_to_circle(binary: np.ndarray, circle: CircleResult) -> np.ndarray:
    """Zero out everything outside the detected circle."""
    mask = np.zeros_like(binary)
    cx, cy, r = int(circle.center_x), int(circle.center_y), int(circle.radius)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    return cv2.bitwise_and(binary, mask)


def _extract_contours(
    masked: np.ndarray,
    min_area: float,
) -> List[np.ndarray]:
    """Return contours filtered by minimum area, as lists of (x, y) int arrays."""
    cnts, _ = cv2.findContours(
        masked, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
    )
    result = []
    for c in cnts:
        if cv2.contourArea(c) >= min_area:
            # shape (N, 1, 2) → (N, 2)
            result.append(c.reshape(-1, 2))
    return result


# ── Contour ordering ──────────────────────────────────────────────────────────

def _greedy_order_contours(contours: List[np.ndarray]) -> List[np.ndarray]:
    """
    Greedy nearest-neighbour sort: start from the first contour's first point,
    always jump to the contour whose first/last endpoint is closest.
    Minimises total pen-up travel.
    """
    if not contours:
        return []

    remaining = [c.copy() for c in contours]
    ordered   = [remaining.pop(0)]

    while remaining:
        last_pt = ordered[-1][-1]
        best_d, best_i, best_flip = math.inf, 0, False

        for i, c in enumerate(remaining):
            d_start = np.linalg.norm(c[0].astype(float) - last_pt.astype(float))
            d_end   = np.linalg.norm(c[-1].astype(float) - last_pt.astype(float))
            if d_start < best_d:
                best_d, best_i, best_flip = d_start, i, False
            if d_end < best_d:
                best_d, best_i, best_flip = d_end, i, True

        chosen = remaining.pop(best_i)
        if best_flip:
            chosen = chosen[::-1]
        ordered.append(chosen)

    return ordered


# ── RDP simplification ────────────────────────────────────────────────────────

def _rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Ramer–Douglas–Peucker polyline simplification."""
    if len(points) < 3:
        return points

    start, end = points[0].astype(float), points[-1].astype(float)
    line = end - start
    line_len = np.linalg.norm(line)

    if line_len < 1e-9:
        dists = np.linalg.norm(points.astype(float) - start, axis=1)
    else:
        # Perpendicular distance from each point to the start→end line
        t = np.dot(points.astype(float) - start, line) / (line_len ** 2)
        proj = start + np.outer(t, line)
        dists = np.linalg.norm(points.astype(float) - proj, axis=1)

    idx = int(np.argmax(dists))
    if dists[idx] > epsilon:
        left  = _rdp(points[:idx + 1], epsilon)
        right = _rdp(points[idx:],     epsilon)
        return np.vstack([left[:-1], right])
    return np.array([points[0], points[-1]])


# ── Coordinate conversion ─────────────────────────────────────────────────────

def _cartesian_to_polar_norm(
    pts: np.ndarray,   # (N, 2) int xy
    cx: float,
    cy: float,
    radius_px: float,
) -> List[Tuple[float, float]]:
    """
    Convert pixel coordinates to normalised polar (theta, r).

    theta ∈ [0, 2π)   — counter-clockwise from +x axis
    r     ∈ [0, 1]    — 1 = detected circle boundary
    """
    result = []
    for x, y in pts.astype(float):
        dx, dy = x - cx, y - cy
        theta = math.atan2(dy, dx) % (2 * math.pi)
        r     = min(math.hypot(dx, dy) / radius_px, 1.0)
        result.append((theta, r))
    return result


# ── Minimum-distance filter ───────────────────────────────────────────────────

def _min_distance_filter(
    points: List[Tuple[float, float]],
    min_px: float,
    radius_px: float,
) -> List[Tuple[float, float]]:
    """Drop points whose arc-distance to the previous kept point is < min_px."""
    if not points:
        return []
    min_norm = min_px / radius_px
    kept = [points[0]]
    for theta, r in points[1:]:
        pt, kt, kr = (theta, r), kept[-1][0], kept[-1][1]
        # Approximate arc distance in normalised units
        dt = abs(theta - kt)
        dt = min(dt, 2 * math.pi - dt)
        dist = math.hypot(dt * r, r - kr)
        if dist >= min_norm:
            kept.append((theta, r))
    return kept


# ── Pen-up insertion ──────────────────────────────────────────────────────────

def _build_waypoints(
    segments: List[List[Tuple[float, float]]],
    theta_jump: float,
    r_jump: float,
) -> List[Waypoint]:
    """
    Flatten ordered segments into a Waypoint list, inserting pen-up moves
    between segments that require a large jump.
    """
    waypoints: List[Waypoint] = []
    prev_theta: Optional[float] = None
    prev_r:     Optional[float] = None

    for seg in segments:
        if not seg:
            continue

        first_theta, first_r = seg[0]

        # Decide if we need to lift the pen before this segment
        needs_lift = False
        if prev_theta is not None:
            dt = abs(first_theta - prev_theta)
            dt = min(dt, 2 * math.pi - dt)
            if dt > theta_jump or abs(first_r - prev_r) > r_jump:
                needs_lift = True

        if needs_lift:
            # Pen-up travel move to the start of this segment
            waypoints.append(Waypoint(theta=first_theta, r=first_r, pen=0))

        for theta, r in seg:
            waypoints.append(Waypoint(theta=theta, r=r, pen=1))
            prev_theta, prev_r = theta, r

    return waypoints


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_path(
    binary: np.ndarray,
    circle: CircleResult,
    symmetry: SymmetryResult,
    cfg: Optional[PathGenConfig] = None,
) -> PathPlan:
    """
    Convert a binary (preprocessed) image and detected circle into a PathPlan.

    Parameters
    ----------
    binary   : uint8 binary image (same size as what circle_detect received)
    circle   : detected circle boundary
    symmetry : symmetry detection result (stored in output metadata)
    cfg      : PathGenConfig

    Returns
    -------
    PathPlan — validated list of waypoints
    """
    if cfg is None:
        cfg = PathGenConfig()

    # 1. Mask to circle interior
    masked = _mask_to_circle(binary, circle)

    # 2. Extract contours
    contours = _extract_contours(masked, cfg.min_contour_area)
    if not contours:
        raise RuntimeError("No drawable contours found inside the circle boundary.")

    # 3. Greedy ordering
    ordered = _greedy_order_contours(contours)

    # 4. RDP simplification + min-distance filter → polar conversion
    segments: List[List[Tuple[float, float]]] = []
    for contour in ordered:
        simplified = _rdp(contour, cfg.rdp_epsilon)
        polar_pts  = _cartesian_to_polar_norm(
            simplified, circle.center_x, circle.center_y, circle.radius
        )
        filtered = _min_distance_filter(polar_pts, cfg.min_segment_px, circle.radius)
        if filtered:
            segments.append(filtered)

    # 5. Build waypoint list with pen-up transitions
    waypoints = _build_waypoints(segments, cfg.pen_up_theta_jump, cfg.pen_up_r_jump)

    # 6. Hard cap
    if len(waypoints) > cfg.max_waypoints:
        # Re-run with tighter RDP
        tighter = PathGenConfig(
            rdp_epsilon=cfg.rdp_epsilon * 2,
            min_segment_px=cfg.min_segment_px * 2,
            min_contour_area=cfg.min_contour_area,
            pen_up_theta_jump=cfg.pen_up_theta_jump,
            pen_up_r_jump=cfg.pen_up_r_jump,
            max_waypoints=cfg.max_waypoints,
        )
        return generate_path(binary, circle, symmetry, tighter)

    plan = PathPlan(
        waypoints=waypoints,
        center_x=circle.center_x,
        center_y=circle.center_y,
        radius_px=circle.radius,
        symmetry_order=symmetry.order,
    )
    return plan


# ── Validation ────────────────────────────────────────────────────────────────

TWO_PI = 2 * math.pi

def validate_path(plan: PathPlan) -> ValidationResult:
    """Check waypoints for range, finiteness, and sanity."""
    errors: List[ValidationError] = []

    if not plan.waypoints:
        errors.append(ValidationError("waypoints", "Empty waypoint list"))
        return ValidationResult(valid=False, errors=errors)

    if len(plan.waypoints) < 3:
        errors.append(ValidationError("waypoints", f"Only {len(plan.waypoints)} waypoints — suspiciously short"))

    for i, w in enumerate(plan.waypoints):
        tag = f"waypoint[{i}]"

        if not math.isfinite(w.theta):
            errors.append(ValidationError(tag, f"theta is non-finite: {w.theta}"))
        elif not (0.0 <= w.theta < TWO_PI):
            errors.append(ValidationError(tag, f"theta out of range: {w.theta:.4f}"))

        if not math.isfinite(w.r):
            errors.append(ValidationError(tag, f"r is non-finite: {w.r}"))
        elif not (0.0 <= w.r <= 1.0):
            errors.append(ValidationError(tag, f"r out of range: {w.r:.4f}"))

        if w.pen not in (0, 1):
            errors.append(ValidationError(tag, f"pen must be 0 or 1, got {w.pen}"))

    # Check for suspiciously large jumps between consecutive pen-down points
    prev: Optional[Waypoint] = None
    for w in plan.waypoints:
        if w.pen == 1 and prev is not None and prev.pen == 1:
            dt = abs(w.theta - prev.theta)
            dt = min(dt, TWO_PI - dt)
            if dt > 1.0:
                errors.append(ValidationError(
                    "waypoints",
                    f"Large pen-down theta jump: {math.degrees(dt):.1f}°"
                ))
        if w.pen == 1:
            prev = w

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# ── Debug visualisation ───────────────────────────────────────────────────────

def draw_path_debug(
    bgr_original: np.ndarray,
    plan: PathPlan,
) -> np.ndarray:
    """Overlay the waypoint path on the original BGR image."""
    out = bgr_original.copy()
    h, w = out.shape[:2]
    cx, cy, r = plan.center_x, plan.center_y, plan.radius_px

    prev_pt: Optional[Tuple[int, int]] = None
    prev_pen = 0

    for wp in plan.waypoints:
        px = int(cx + wp.r * r * math.cos(wp.theta))
        py = int(cy + wp.r * r * math.sin(wp.theta))
        px = max(0, min(w - 1, px))
        py = max(0, min(h - 1, py))

        if prev_pt is not None:
            color = (0, 200, 255) if wp.pen == 1 else (80, 80, 80)
            cv2.line(out, prev_pt, (px, py), color, 1, cv2.LINE_AA)

        prev_pt  = (px, py)
        prev_pen = wp.pen

    # Draw circle boundary
    cv2.circle(out, (int(cx), int(cy)), int(r), (0, 255, 0), 1)

    label = (f"Waypoints: {len(plan.waypoints)}  "
             f"Sym: {plan.symmetry_order}-fold")
    cv2.putText(out, label, (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out
