"""
cv/vectorize.py — image → Cartesian-cm waypoint path for a mobile 2WD robot.

This is the new entry point that the web app's /api/designs/vectorize calls
into. It replaces the *image-input* side of the legacy polar pipeline
(cv/path_gen.py) and outputs waypoints in real-world centimetres centred
on the design — the coordinate system the mobile robot actually drives in.

Pipeline
--------
1. Decode image (PNG/JPEG) → OpenCV BGR
2. Preprocess: grayscale → Otsu threshold → morphological cleanup
3. Find the outer circular boundary (Hough Circle Transform, with graceful
   fallbacks if it can't find a confident circle)
4. Extract contours inside the circle
5. Greedy-order the contours (minimise pen-up travel)
6. Simplify each contour with Ramer–Douglas–Peucker
7. Convert pixel coordinates → centimetres, with the design centred at (0, 0)
8. Insert pen-up waypoints between disjoint segments
9. Estimate waypoint count and drawing time

The output dict matches what /api/designs/vectorize expects in server/routes/designs.py.
"""
from __future__ import annotations

import base64
import io
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class VectorizeConfig:
    """Tuning knobs for the vectorize pipeline."""
    rdp_epsilon_px:        float = 2.0    # RDP simplification tolerance
    min_segment_px:        float = 6.0    # min distance between kept points
    min_contour_area_px2:  float = 40.0   # drop tiny noise contours
    pen_up_dist_cm:        float = 1.5    # gap that triggers a pen-up
    max_waypoints:         int   = 3000   # safety cap
    drawing_speed_wps:     int   = 40     # for time estimate (waypoints/sec)
    circle_fallback_radius_ratio: float = 0.42  # used if Hough fails


# ── Public entry point ───────────────────────────────────────────────────────

def vectorize_image(
    *,
    image_bytes: bytes,
    canvas_cm: float = 60.0,
    cfg: Optional[VectorizeConfig] = None,
) -> dict:
    """
    Run the full image→waypoint pipeline. Returns a dict shaped to match
    the server-side response — see server.routes.designs.vectorize.

    Parameters
    ----------
    image_bytes : raw PNG/JPEG/WebP bytes from the design candidate
    canvas_cm   : real-world edge length of the drawing area in cm
    cfg         : optional VectorizeConfig (defaults are fine for a first pass)

    Returns
    -------
    dict with keys: center_x_cm, center_y_cm, radius_cm, waypoints,
                    estimated_waypoints, estimated_drawing_time_sec,
                    original_bgr, traced_bgr

    Raises
    ------
    RuntimeError on unrecoverable issues (no contours, decode failure, etc.)
    """
    if cfg is None:
        cfg = VectorizeConfig()

    # ── 1. Decode ────────────────────────────────────────────────────────────
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("Could not decode the image. The file may be corrupt.")

    h, w = bgr.shape[:2]
    log.info("Vectorize: decoded %dx%d image, canvas=%.1f cm", w, h, canvas_cm)

    # ── 2. Preprocess (grayscale → Otsu → morphology) ─────────────────────────
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Light cleanup: close small gaps, open speckles
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    # ── 3. Find the circle (Hough, with safe fallback) ───────────────────────
    circle = _find_circle(bgr, gray, cfg)
    cx, cy, r_px = circle

    # ── 4. Mask to the interior of the circle ────────────────────────────────
    mask = np.zeros_like(binary)
    cv2.circle(mask, (cx, cy), r_px, 255, -1)
    interior = cv2.bitwise_and(binary, mask)

    # ── 5. Contours inside the circle ────────────────────────────────────────
    cnts, _ = cv2.findContours(interior, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    contours: List[np.ndarray] = [
        c.reshape(-1, 2) for c in cnts
        if cv2.contourArea(c) >= cfg.min_contour_area_px2
    ]
    if not contours:
        raise RuntimeError(
            "No drawable shapes found inside the pookalam. "
            "Try regenerating with fewer details."
        )

    # ── 6. Greedy-order the contours ─────────────────────────────────────────
    ordered = _greedy_order_contours(contours)

    # ── 7. Simplify (RDP) ────────────────────────────────────────────────────
    simplified: List[np.ndarray] = []
    for c in ordered:
        s = _rdp(c, cfg.rdp_epsilon_px)
        if len(s) >= 2:
            simplified.append(s)

    if not simplified:
        raise RuntimeError("Contours simplified to nothing — design has no drawable strokes.")

    # ── 8. Pixel → centimetres ───────────────────────────────────────────────
    # We want the design centred at (0, 0) and to fit inside ±canvas_cm/2.
    # Pixels-per-cm = image_width / canvas_cm (assuming the image is the
    # whole canvas — which is true for our generated images).
    px_per_cm = w / canvas_cm
    cx_cm, cy_cm = 0.0, 0.0
    r_cm = r_px / px_per_cm

    def _to_cm(pt: Tuple[int, int]) -> Tuple[float, float]:
        # Flip Y so the robot's "forward" is screen-down. Image Y grows down,
        # robot Y typically grows forward. Pick one and be consistent.
        x_cm = (pt[0] - cx) / px_per_cm
        y_cm = (pt[1] - cy) / px_per_cm
        return x_cm, y_cm

    # ── 9. Min-distance filter + pen-up insertion ────────────────────────────
    waypoints: List[dict] = []
    prev_end: Optional[Tuple[float, float]] = None
    pen_up_threshold_px = cfg.pen_up_dist_cm * px_per_cm
    last_was_pen_up = True  # start with pen up

    for contour in simplified:
        # Min-distance filter
        kept_px: List[Tuple[int, int]] = [tuple(contour[0])]
        for pt in contour[1:]:
            pt_t = tuple(pt)
            if _pixel_dist(kept_px[-1], pt_t) >= cfg.min_segment_px:
                kept_px.append(pt_t)
        if len(kept_px) < 2:
            continue

        # Pen-up if we're jumping a long way to start this segment
        if prev_end is not None and last_was_pen_up is False:
            jump_cm = math.hypot(
                (kept_px[0][0] - cx) / px_per_cm - prev_end[0],
                (kept_px[0][1] - cy) / px_per_cm - prev_end[1],
            )
            if jump_cm > cfg.pen_up_dist_cm:
                waypoints.append({
                    "x": (kept_px[0][0] - cx) / px_per_cm,
                    "y": (kept_px[0][1] - cy) / px_per_cm,
                    "pen": 0,
                })
                last_was_pen_up = True

        for px, py in kept_px:
            x_cm = (px - cx) / px_per_cm
            y_cm = (py - cy) / px_per_cm
            waypoints.append({"x": x_cm, "y": y_cm, "pen": 1})
            prev_end = (x_cm, y_cm)
            last_was_pen_up = False

    if len(waypoints) > cfg.max_waypoints:
        # Could re-run with a tighter RDP, but for the hackathon path
        # just report it as "too complex" and let the UI ask for a regen.
        raise RuntimeError(
            f"Design produced {len(waypoints)} waypoints "
            f"(max {cfg.max_waypoints}). Try fewer petals or simpler complexity."
        )

    # ── 10. Traced-overlay debug image (BGR) ─────────────────────────────────
    traced_bgr = bgr.copy()
    cv2.circle(traced_bgr, (cx, cy), r_px, (0, 200, 255), 2)        # amber
    cv2.circle(traced_bgr, (cx, cy), 4,            (0, 0, 255),   -1)
    for contour in simplified:
        pts = contour.reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(traced_bgr, [pts], isClosed=True,
                      color=(180, 105, 30), thickness=1)  # marigold

    n_strokes = sum(
        1 for i, w in enumerate(waypoints)
        if w["pen"] == 1 and (i == 0 or waypoints[i - 1]["pen"] == 0)
    )
    estimated_time = max(5, len(waypoints) // cfg.drawing_speed_wps)

    return {
        "center_x_cm": cx_cm,
        "center_y_cm": cy_cm,
        "radius_cm":   r_cm,
        "waypoints":   waypoints,
        "estimated_waypoints":        len(waypoints),
        "estimated_drawing_time_sec": estimated_time,
        "original_bgr": bgr,
        "traced_bgr":   traced_bgr,
    }


# ── Internal helpers ─────────────────────────────────────────────────────────

def _find_circle(
    bgr: np.ndarray, gray: np.ndarray, cfg: VectorizeConfig,
) -> Tuple[int, int, int]:
    """
    Find the outer circular boundary of the pookalam. Returns (cx, cy, r) in
    pixels. Falls back gracefully when Hough can't find a confident circle —
    Gemini-generated images always have a roughly centred design, so a
    centre-of-image + fixed-radius fallback is reasonable.
    """
    h, w = gray.shape[:2]
    min_dim = min(h, w)

    working = cv2.medianBlur(gray, 5)
    raw = cv2.HoughCircles(
        working,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=int(min_dim * 0.5),
        param1=120,
        param2=30,
        minRadius=int(min_dim * 0.2),
        maxRadius=int(min_dim * 0.5),
    )

    if raw is not None and len(raw[0]) > 0:
        # Take the circle closest to the image centre and biggest reasonable radius
        best = max(
            raw[0],
            key=lambda c: (
                -abs(float(c[0]) - w / 2) - abs(float(c[1]) - h / 2),  # close to centre
                float(c[2]),                                            # bigger
            ),
        )
        return int(best[0]), int(best[1]), int(best[2])

    # Fallback: assume the design fills most of the canvas, centred
    cx = w // 2
    cy = h // 2
    r  = int(min_dim * cfg.circle_fallback_radius_ratio)
    log.warning("Hough circle detection failed — using image-centre fallback (r=%d px)", r)
    return cx, cy, r


def _greedy_order_contours(contours: List[np.ndarray]) -> List[np.ndarray]:
    """Greedy nearest-neighbour sort, same idea as cv/path_gen.py."""
    if not contours:
        return []
    remaining = [c.copy() for c in contours]
    ordered = [remaining.pop(0)]
    while remaining:
        last_pt = ordered[-1][-1].astype(float)
        best_d, best_i, best_flip = math.inf, 0, False
        for i, c in enumerate(remaining):
            d_start = np.linalg.norm(c[0].astype(float) - last_pt)
            d_end   = np.linalg.norm(c[-1].astype(float) - last_pt)
            if d_start < best_d:
                best_d, best_i, best_flip = d_start, i, False
            if d_end < best_d:
                best_d, best_i, best_flip = d_end, i, True
        chosen = remaining.pop(best_i)
        if best_flip:
            chosen = chosen[::-1]
        ordered.append(chosen)
    return ordered


def _rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Ramer–Douglas–Peucker polyline simplification (vectorized)."""
    if len(points) < 3:
        return points
    start = points[0].astype(float)
    end   = points[-1].astype(float)
    line  = end - start
    line_len = np.linalg.norm(line)
    if line_len < 1e-9:
        dists = np.linalg.norm(points.astype(float) - start, axis=1)
    else:
        t = np.dot(points.astype(float) - start, line) / (line_len ** 2)
        proj = start + np.outer(t, line)
        dists = np.linalg.norm(points.astype(float) - proj, axis=1)
    idx = int(np.argmax(dists))
    if dists[idx] > epsilon:
        left  = _rdp(points[:idx + 1], epsilon)
        right = _rdp(points[idx:],     epsilon)
        return np.vstack([left[:-1], right])
    return np.array([points[0], points[-1]])


def _pixel_dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
