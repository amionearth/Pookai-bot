"""
Smoke tests for ai.gemini_client — no real API key required.

Verifies
--------
- Prompt builder produces 3 visibly different prompts for the same params
- Prompt correctly interpolates petal/layer/color/free_text values
- Response parser correctly extracts the first inline image
- Response parser returns None for an empty / malformed response
- resolve_api_key() falls back from GEMINI_API_KEY to AI_API_KEY
- generate_pookalam_images() raises ValueError when no key is set

Run: python -m pytest ai/tests/test_gemini_client.py -v
     (pytest is in requirements-cv.txt)
"""
from __future__ import annotations

import pytest

from ai.gemini_client import (
    _build_prompt,
    _extract_image,
    generate_pookalam_images,
    resolve_api_key,
    GeminiImage,
)


# ── Prompt builder ────────────────────────────────────────────────────────────

def test_prompts_differ_per_variant():
    a = _build_prompt(petal_count=8, layer_count=2, color_count=3, free_text="lotus", variant=0)
    b = _build_prompt(petal_count=8, layer_count=2, color_count=3, free_text="lotus", variant=1)
    c = _build_prompt(petal_count=8, layer_count=2, color_count=3, free_text="lotus", variant=2)
    assert a != b != c
    assert "lotus" in a.lower()


def test_prompt_includes_numeric_params():
    p = _build_prompt(petal_count=12, layer_count=3, color_count=5, free_text="", variant=0)
    assert "12-fold"   in p
    assert "layer"     in p.lower()
    assert "5"         in p
    assert "no additional description" in p.lower()  # empty free_text handled


def test_prompt_includes_user_free_text():
    p = _build_prompt(petal_count=8, layer_count=2, color_count=3, free_text="kerala temple", variant=0)
    assert "kerala temple" in p


def test_prompt_includes_fixed_constraints():
    """The fixed developer prompt contains the rules the downstream pipeline depends on."""
    p = _build_prompt(petal_count=6, layer_count=2, color_count=3, free_text="", variant=0)
    for must_have in [
        "white background",
        "circular boundary",
        "No text",
        "closed outline",
    ]:
        assert must_have.lower() in p.lower(), f"prompt missing constraint: {must_have}"


# ── Response parser ───────────────────────────────────────────────────────────

def _fake_b64_png() -> str:
    # 1×1 transparent PNG
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
    )


def test_extract_image_happy_path():
    payload = {
        "candidates": [
            {"content": {"parts": [
                {"text": "A pretty Pookalam."},
                {"inlineData": {"mimeType": "image/png", "data": _fake_b64_png()}},
            ]}}
        ]
    }
    out = _extract_image(payload)
    assert isinstance(out, GeminiImage)
    assert out.mime_type == "image/png"
    assert out.caption.startswith("A pretty")
    assert out.image_bytes.startswith(b"\x89PNG")


def test_extract_image_no_candidates():
    assert _extract_image({"candidates": []}) is None


def test_extract_image_only_text():
    payload = {"candidates": [{"content": {"parts": [{"text": "Sorry"}]}}]}
    assert _extract_image(payload) is None


def test_extract_image_empty_inline_data():
    payload = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": ""}}
    ]}}]}
    assert _extract_image(payload) is None


# ── API key resolution ────────────────────────────────────────────────────────

def test_resolve_api_key_explicit(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    assert resolve_api_key("explicit-key") == "explicit-key"


def test_resolve_api_key_from_gemini_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-gemini")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    assert resolve_api_key() == "from-gemini"


def test_resolve_api_key_falls_back_to_ai_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AI_API_KEY", "legacy-key")
    assert resolve_api_key() == "legacy-key"


def test_resolve_api_key_none_when_unset(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    assert resolve_api_key() is None


# ── generate_pookalam_images guard ────────────────────────────────────────────

def test_generate_raises_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    import asyncio
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        asyncio.run(generate_pookalam_images(
            petal_count=8, layer_count=2, color_count=3, free_text="",
        ))
