"""
symmetry.py — rotational symmetry detection via polar-domain autocorrelation.

Convention
----------
theta : [0, 2π)  — counter-clockwise from the positive x-axis
r     : [0, radius_px]

Algorithm
---------
1. Build a 1-D angular projection by collapsing the polar image along the
   radial axis (summing intensities at each angle bin).
2. Compute the circular autocorrelation of that signal.
3. Search for the lag that maximises the autocorrelation for each candidate
   symmetry order n (lag = theta_bins / n).
4. Select the order with the highest normalised autocorrelation peak.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List
import cv2
import numpy as np

from .models import PolarRepresentation, SymmetryResult


# ── Polar unwrapping ──────────────────────────────────────────────────────────

def build_polar(
    gray: np.ndarray,
    cx: float,
    cy: float,
    radius_px: float,
    theta_bins: int = 720,
    r_bins: int = 256,
) -> PolarRepresentation:
    """
    Remap a grayscale image into (r_bins × theta_bins) polar coordinates
    centred at (cx, cy) with maximum radius radius_px.

    Returns a PolarRepresentation whose .image has shape (r_bins, theta_bins).
    """
    h, w = gray.shape[:2]

    # Build destination grid
    thetas = np.linspace(0, 2 * np.pi, theta_bins, endpoint=False)
    rs     = np.linspace(0, radius_px, r_bins)

    TH, R = np.meshgrid(thetas, rs)          # both (r_bins, theta_bins)
    src_x = (cx + R * np.cos(TH)).astype(np.float32)
    src_y = (cy + R * np.sin(TH)).astype(np.float32)

    polar = cv2.remap(
        gray.astype(np.float32),
        src_x, src_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return PolarRepresentation(
        image=polar.astype(np.uint8),
        theta_bins=theta_bins,
        r_bins=r_bins,
        center_x=cx,
        center_y=cy,
        radius_px=radius_px,
    )


# ── Angular projection ────────────────────────────────────────────────────────

def angular_projection(polar_img: np.ndarray) -> np.ndarray:
    """
    Collapse the radial axis of a polar image by summing along rows.
    Returns a 1-D array of length theta_bins.
    """
    proj = polar_img.astype(np.float64).sum(axis=0)
    # Normalise to zero mean for cleaner autocorrelation
    proj -= proj.mean()
    return proj


# ── Circular autocorrelation ──────────────────────────────────────────────────

def circular_autocorrelation(signal: np.ndarray) -> np.ndarray:
    """
    Compute the circular autocorrelation of a 1-D signal using FFT.
    Result is normalised so the zero-lag value is 1.0.
    """
    n = len(signal)
    F = np.fft.rfft(signal, n=n)
    acf = np.fft.irfft(F * np.conj(F), n=n)
    # Normalise
    if acf[0] != 0:
        acf /= acf[0]
    return acf


# ── Symmetry detection ────────────────────────────────────────────────────────

@dataclass
class SymmetryConfig:
    min_order: int = 2
    max_order: int = 24
    theta_bins: int = 720
    r_bins: int = 256


def detect_symmetry(
    polar: PolarRepresentation,
    cfg: Optional[SymmetryConfig] = None,
) -> SymmetryResult:
    """
    Estimate the dominant rotational symmetry order of a Pookalam.

    Algorithm
    ---------
    Rather than ACF averaging (which suffers from harmonic aliasing — order 4
    scores equally well for an 8-fold pattern because 4 divides 8), we work
    directly in the frequency domain:

    1. Compute the power spectrum of the angular projection.
    2. For each candidate order n, the expected frequency bin is exactly n
       (cycles per full revolution).
    3. The candidate with the highest power at its fundamental bin wins.
    4. Confidence = that peak power / total signal power.

    This correctly distinguishes 8-fold from 4-fold because the 8-fold pattern
    has power concentrated at bin 8, not bin 4.

    Parameters
    ----------
    polar : PolarRepresentation from build_polar()
    cfg   : SymmetryConfig

    Returns
    -------
    SymmetryResult with order, confidence, angular_period_rad
    """
    if cfg is None:
        cfg = SymmetryConfig()

    proj = angular_projection(polar.image)
    N    = len(proj)

    # Power spectrum (magnitudes of rfft)
    spectrum = np.abs(np.fft.rfft(proj, n=N)) ** 2
    total_power = spectrum[1:].sum() + 1e-9  # exclude DC; avoid div-by-zero

    best_order      = 1
    best_confidence = -1.0

    for order in range(cfg.min_order, cfg.max_order + 1):
        # The fundamental frequency bin for this rotational order
        # (the signal repeats `order` times per revolution)
        if order >= len(spectrum):
            continue
        score = float(spectrum[order]) / total_power

        if score > best_confidence:
            best_confidence = score
            best_order      = order

    # Clamp confidence to [0, 1]
    best_confidence = max(0.0, min(1.0, best_confidence))
    period_rad = 2 * np.pi / best_order

    return SymmetryResult(
        order=best_order,
        confidence=best_confidence,
        angular_period_rad=period_rad,
    )


# ── Debug visualisation ───────────────────────────────────────────────────────

def draw_symmetry_debug(
    polar: PolarRepresentation,
    result: SymmetryResult,
) -> np.ndarray:
    """
    Build a side-by-side debug image showing:
      left  — polar-unwrapped image
      right — angular projection + ACF with detected period marked
    """
    h, w = polar.image.shape[:2]

    # --- Plot panel (same height as polar image) ---
    panel_w = 512
    panel = np.zeros((h, panel_w), dtype=np.uint8)

    proj = angular_projection(polar.image)
    acf  = circular_autocorrelation(proj)

    def _draw_signal(signal, y_offset, row_height, color=200):
        sig_norm = (signal - signal.min()) / (signal.max() - signal.min() + 1e-9)
        for i in range(len(sig_norm) - 1):
            x1 = int(i * panel_w / len(sig_norm))
            x2 = int((i + 1) * panel_w / len(sig_norm))
            y1 = y_offset + row_height - int(sig_norm[i] * row_height)
            y2 = y_offset + row_height - int(sig_norm[i + 1] * row_height)
            cv2.line(panel, (x1, y1), (x2, y2), color, 1)

    half = h // 2
    _draw_signal(proj, 0,    half - 4, 180)
    _draw_signal(acf,  half, half - 4, 220)

    # Mark detected period on ACF panel
    period_bins = int(len(acf) / result.order)
    if 0 < period_bins < panel_w:
        px = int(period_bins * panel_w / len(acf))
        cv2.line(panel, (px, half), (px, h), 255, 1)

    # Labels (white text)
    cv2.putText(panel, "Angular projection", (4, 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1, cv2.LINE_AA)
    cv2.putText(panel, "Autocorrelation", (4, half + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1, cv2.LINE_AA)
    cv2.putText(panel,
                f"Symmetry order: {result.order}  conf: {result.confidence:.2f}",
                (4, h - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1, cv2.LINE_AA)

    # Combine polar image + plot panel side by side
    combined = np.hstack([polar.image, panel])
    return combined
