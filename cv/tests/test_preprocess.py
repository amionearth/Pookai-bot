"""Tests for preprocess.py — no hardware required."""
import numpy as np
import pytest
import cv2

from cv.preprocess import (
    load_image, resize_preserve_aspect, to_gray,
    denoise, enhance_contrast, threshold, morphological_cleanup,
    preprocess_image, PreprocessConfig,
)


def _make_bgr(h=200, w=300) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (w // 2, h // 2), min(h, w) // 3, (200, 100, 50), -1)
    return img


# ── load_image ────────────────────────────────────────────────────────────────

def test_load_image_missing():
    with pytest.raises(FileNotFoundError, match="Cannot load"):
        load_image("does_not_exist.jpg")


# ── resize_preserve_aspect ────────────────────────────────────────────────────

def test_resize_preserves_aspect():
    img = _make_bgr(400, 600)
    out = resize_preserve_aspect(img, max_dimension=300)
    h, w = out.shape[:2]
    assert max(h, w) == 300
    assert abs(w / h - 600 / 400) < 0.02


def test_resize_no_upscale():
    img = _make_bgr(100, 150)
    out = resize_preserve_aspect(img, max_dimension=800)
    assert out.shape[:2] == (100, 150)


# ── to_gray ───────────────────────────────────────────────────────────────────

def test_to_gray_from_bgr():
    img = _make_bgr()
    gray = to_gray(img)
    assert gray.ndim == 2


def test_to_gray_passthrough():
    gray = np.zeros((100, 100), dtype=np.uint8)
    out = to_gray(gray)
    assert out.shape == (100, 100)


# ── denoise ───────────────────────────────────────────────────────────────────

def test_denoise_zero_kernel_passthrough():
    gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    out = denoise(gray, 0)
    np.testing.assert_array_equal(out, gray)


def test_denoise_reduces_noise():
    noisy = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    smooth = denoise(noisy, 9)
    # Variance should decrease
    assert smooth.var() < noisy.var()


# ── threshold ────────────────────────────────────────────────────────────────

def test_threshold_otsu_binary():
    gray = to_gray(_make_bgr())
    binary = threshold(gray, "otsu")
    vals = np.unique(binary)
    assert set(vals).issubset({0, 255})


def test_threshold_adaptive_binary():
    gray = to_gray(_make_bgr())
    binary = threshold(gray, "adaptive")
    vals = np.unique(binary)
    assert set(vals).issubset({0, 255})


def test_threshold_none_passthrough():
    gray = to_gray(_make_bgr())
    out = threshold(gray, "none")
    np.testing.assert_array_equal(out, gray)


def test_threshold_invalid():
    gray = to_gray(_make_bgr())
    with pytest.raises(ValueError, match="Unknown threshold"):
        threshold(gray, "bogus")


# ── preprocess_image (integration) ───────────────────────────────────────────

def test_preprocess_returns_image_and_intermediates():
    img = _make_bgr()
    cfg = PreprocessConfig()
    out, intermediates = preprocess_image(img, cfg)
    assert out is not None
    assert "original" in intermediates
    assert "cleaned"  in intermediates
    assert out.ndim == 2


def test_preprocess_invalid_path():
    with pytest.raises(FileNotFoundError):
        preprocess_image("nonexistent_file.png")
