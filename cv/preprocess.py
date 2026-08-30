"""
preprocess.py — configurable image preprocessing for Pookalam photographs.

Each function is small and independently usable.  The main entry point,
``preprocess_image``, chains them according to a ``PreprocessConfig``.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import cv2
import numpy as np


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class PreprocessConfig:
    max_dimension: int = 800          # longest edge after resize
    blur_kernel: int = 5              # Gaussian kernel size (odd); 0 = skip
    clahe_clip: float = 2.0           # CLAHE clip limit; 0 = skip
    clahe_grid: int = 8               # CLAHE tile grid size
    threshold_method: str = "otsu"    # "otsu" | "adaptive" | "none"
    adaptive_block: int = 31          # adaptive threshold block size (odd)
    adaptive_c: int = 5               # adaptive threshold constant
    morph_open_kernel: int = 3        # morphological open kernel; 0 = skip
    morph_close_kernel: int = 5       # morphological close kernel; 0 = skip


# ── Individual steps ──────────────────────────────────────────────────────────

def load_image(path: str) -> np.ndarray:
    """Load an image from disk; raise on failure."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path!r}")
    return img


def resize_preserve_aspect(
    img: np.ndarray, max_dimension: int
) -> np.ndarray:
    """Resize so the longest edge equals *max_dimension*; keep aspect ratio."""
    h, w = img.shape[:2]
    if max(h, w) <= max_dimension:
        return img.copy()
    scale = max_dimension / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def to_gray(img: np.ndarray) -> np.ndarray:
    """Convert BGR → grayscale (no-op if already single-channel)."""
    if len(img.shape) == 2:
        return img.copy()
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray, kernel_size: int) -> np.ndarray:
    """Apply Gaussian blur for denoising."""
    if kernel_size <= 0:
        return gray.copy()
    k = kernel_size | 1  # ensure odd
    return cv2.GaussianBlur(gray, (k, k), 0)


def enhance_contrast(gray: np.ndarray, clip: float, grid: int) -> np.ndarray:
    """Apply CLAHE contrast enhancement."""
    if clip <= 0:
        return gray.copy()
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    return clahe.apply(gray)


def threshold(
    gray: np.ndarray,
    method: str,
    adaptive_block: int = 31,
    adaptive_c: int = 5,
) -> np.ndarray:
    """
    Binarise the image.

    method: "otsu" | "adaptive" | "none"
    Returns a binary image (0 or 255).
    """
    if method == "none":
        return gray.copy()
    if method == "otsu":
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        return binary
    if method == "adaptive":
        block = adaptive_block | 1  # must be odd
        return cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block, adaptive_c,
        )
    raise ValueError(f"Unknown threshold method: {method!r}")


def morphological_cleanup(
    binary: np.ndarray, open_k: int, close_k: int
) -> np.ndarray:
    """Remove noise (open) and fill small gaps (close)."""
    result = binary.copy()
    if open_k > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (open_k, open_k)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
    if close_k > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (close_k, close_k)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
    return result


# ── Main pipeline ─────────────────────────────────────────────────────────────

def preprocess_image(
    source: str | np.ndarray,
    cfg: Optional[PreprocessConfig] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Run the full preprocessing pipeline.

    Parameters
    ----------
    source : path string or BGR ndarray
    cfg    : PreprocessConfig (uses defaults if None)

    Returns
    -------
    processed : uint8 grayscale (or binary) image ready for CV stages
    intermediates : dict of labelled intermediate images for debug output
    """
    if cfg is None:
        cfg = PreprocessConfig()

    intermediates: Dict[str, np.ndarray] = {}

    # 1. Load
    if isinstance(source, str):
        img_bgr = load_image(source)
    else:
        img_bgr = source.copy()
    intermediates["original"] = img_bgr

    # 2. Resize
    img_bgr = resize_preserve_aspect(img_bgr, cfg.max_dimension)
    intermediates["resized"] = img_bgr

    # 3. Grayscale
    gray = to_gray(img_bgr)

    # 4. Denoise
    gray = denoise(gray, cfg.blur_kernel)
    intermediates["denoised"] = gray

    # 5. Contrast enhancement
    gray = enhance_contrast(gray, cfg.clahe_clip, cfg.clahe_grid)
    intermediates["contrast"] = gray

    # 6. Threshold / segmentation
    binary = threshold(
        gray, cfg.threshold_method, cfg.adaptive_block, cfg.adaptive_c
    )
    intermediates["threshold"] = binary

    # 7. Morphological cleanup
    cleaned = morphological_cleanup(binary, cfg.morph_open_kernel, cfg.morph_close_kernel)
    intermediates["cleaned"] = cleaned

    return cleaned, intermediates
