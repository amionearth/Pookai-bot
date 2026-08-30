"""
circle_detect.py — Pookalam boundary detection via Hough Circle Transform.

Returns the single best-fit circle representing the outer boundary of the
Pookalam.  Includes a debug image and raises a descriptive error when no
confident circle can be found.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np

from .models import CircleResult


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class CircleDetectConfig:
    dp: float = 1.2           # inverse accumulator resolution ratio
    min_dist_ratio: float = 0.3   # min distance between centres as fraction of image height
    param1: float = 100       # Canny high threshold
    param2: float = 30        # accumulator threshold (lower → more circles, more false pos)
    min_radius_ratio: float = 0.15  # min radius as fraction of min(h, w)
    max_radius_ratio: float = 0.55  # max radius as fraction of min(h, w)
    blur_before: int = 7      # extra Gaussian blur before HoughCircles (odd); 0 = skip
    confidence_threshold: float = 0.25  # below this → detection is considered failed


# ── Score / select the best circle ───────────────────────────────────────────

def _score_circle(
    gray: np.ndarray,
    cx: float, cy: float, r: float,
) -> float:
    """
    Score a candidate circle by measuring how much of its circumference
    falls on strong edges.  Returns value in [0, 1].
    """
    h, w = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)

    # Sample points around the circle circumference
    n_samples = max(64, int(2 * np.pi * r))
    angles = np.linspace(0, 2 * np.pi, n_samples, endpoint=False)
    xs = (cx + r * np.cos(angles)).astype(int)
    ys = (cy + r * np.sin(angles)).astype(int)

    # Clamp to image bounds
    valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    if valid.sum() == 0:
        return 0.0

    hit = edges[ys[valid], xs[valid]] > 0
    return float(hit.sum()) / float(valid.sum())


def _pick_best_circle(
    circles: np.ndarray,  # shape (N, 3): [cx, cy, r]
    gray: np.ndarray,
) -> Tuple[int, float]:
    """Return (index, score) of the best circle."""
    scores = [
        _score_circle(gray, float(c[0]), float(c[1]), float(c[2]))
        for c in circles
    ]
    best_idx = int(np.argmax(scores))
    return best_idx, scores[best_idx]


# ── Main detection ────────────────────────────────────────────────────────────

def detect_circle(
    gray: np.ndarray,
    cfg: Optional[CircleDetectConfig] = None,
) -> CircleResult:
    """
    Detect the dominant circle in a grayscale image.

    Parameters
    ----------
    gray : uint8 grayscale image (already resized/enhanced)
    cfg  : CircleDetectConfig — pass None to use defaults

    Returns
    -------
    CircleResult with center, radius, confidence

    Raises
    ------
    RuntimeError if no circle meets the confidence threshold
    """
    if cfg is None:
        cfg = CircleDetectConfig()

    h, w = gray.shape[:2]
    min_dim = min(h, w)

    # Optional extra blur to smooth out texture before Hough
    working = gray.copy()
    if cfg.blur_before > 0:
        k = cfg.blur_before | 1
        working = cv2.GaussianBlur(working, (k, k), 0)

    min_r = int(min_dim * cfg.min_radius_ratio)
    max_r = int(min_dim * cfg.max_radius_ratio)
    min_dist = int(h * cfg.min_dist_ratio)

    raw = cv2.HoughCircles(
        working,
        cv2.HOUGH_GRADIENT,
        dp=cfg.dp,
        minDist=min_dist,
        param1=cfg.param1,
        param2=cfg.param2,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if raw is None or len(raw[0]) == 0:
        raise RuntimeError(
            "HoughCircles found no candidates. "
            "Try lowering param2, adjusting min/max_radius_ratio, "
            "or improving preprocessing contrast."
        )

    candidates = raw[0]  # shape (N, 3)
    best_idx, score = _pick_best_circle(candidates, working)

    if score < cfg.confidence_threshold:
        raise RuntimeError(
            f"Best circle candidate has confidence {score:.2f} < "
            f"threshold {cfg.confidence_threshold:.2f}. "
            "The image may not contain a clear circular boundary. "
            "Try --threshold or --radius overrides."
        )

    cx, cy, r = candidates[best_idx]
    return CircleResult(
        center_x=float(cx),
        center_y=float(cy),
        radius=float(r),
        confidence=score,
    )


# ── Debug visualisation ───────────────────────────────────────────────────────

def draw_circle_debug(
    bgr: np.ndarray,
    result: CircleResult,
) -> np.ndarray:
    """
    Overlay the detected circle and centre on a BGR image.
    Returns a new annotated BGR image.
    """
    out = bgr.copy()
    cx, cy, r = int(result.center_x), int(result.center_y), int(result.radius)

    # Outer circle
    cv2.circle(out, (cx, cy), r, (0, 255, 0), 2)
    # Centre crosshair
    cv2.circle(out, (cx, cy), 4, (0, 0, 255), -1)
    cv2.line(out, (cx - 15, cy), (cx + 15, cy), (0, 0, 255), 1)
    cv2.line(out, (cx, cy - 15), (cx, cy + 15), (0, 0, 255), 1)

    label = f"r={r}px  conf={result.confidence:.2f}"
    cv2.putText(
        out, label, (cx - r, cy - r - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA,
    )
    return out
