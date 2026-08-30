"""
ai/gemini_client.py — PookalBot Gemini AI Design & Vector Generation Engine.

Features:
  - Direct Google AI Studio Gemini API (gemini-2.0-flash, gemini-1.5-flash, gemini-2.5-flash)
  - Cultural Gemini Prompting: Returns structured geometric Pookalam specifications
  - Vector SVG to High-Resolution B&W line art converter
  - Multimodal fallback (Pollinations FLUX & Procedural engine)
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

import cv2
import httpx
import numpy as np

log = logging.getLogger(__name__)

# ── Environment Keys ─────────────────────────────────────────────────────────

_GEMINI_KEY_ENV = "GEMINI_API_KEY"

# ── Color Palettes for SVG Render ──────────────────────────────────────────

PALETTES = {
    "traditional": ["#c8860a", "#2e7d32", "#7b1fa2", "#e65100"],
    "floral":      ["#e91e63", "#ff9800", "#4caf50", "#9c27b0"],
    "geometric":   ["#1565c0", "#00695c", "#f57f17", "#6a1b9a"],
    "modern":      ["#37474f", "#00acc1", "#ff7043", "#66bb6a"],
    "festival":    ["#d32f2f", "#f57c00", "#388e3c", "#7b1fa2"],
    "minimal":     ["#000000", "#333333", "#555555", "#777777"],
}

def _pal(style: str, idx: int) -> str:
    cols = PALETTES.get(style, PALETTES["traditional"])
    return cols[idx % len(cols)]

def _pt(cx, cy, r, angle):
    return cx + r * math.cos(angle), cy + r * math.sin(angle)


# ── Structured Gemini System Prompt ─────────────────────────────────────────

GEMINI_SYSTEM_PROMPT = """You are an expert in traditional Kerala Pookalam (floral rangoli) art, Onam cultural traditions, and geometry.
Your job is to generate mathematically distinct, beautiful, and robot-drawable Pookalam designs in structured JSON.

IMPORTANT RULES:
- The designs MUST genuinely reflect the user's specific theme/prompt (e.g. Mahabali, Kathakali, Vallam Kali, Thiruvathira, Peacock, Star, Lotus, Geometric).
- Use mathematical geometry: concentric rings, radial petals, polygons, stars.
- All numeric values must be valid and robot-drawable.
- Return ONLY a valid JSON array with 3 distinct design objects. No markdown, no code fences.

JSON Schema per object:
{
  "name": "Design Name (max 4 words)",
  "description": "Cultural connection to Kerala Onam and the theme",
  "symmetry": "N-fold",
  "complexity": "simple|medium|detailed",
  "motifs": ["list", "of", "motifs"],
  "rings": [outer_radius, mid_radius, inner_radius],
  "petals": N_integer,
  "inner_petals": N_integer,
  "outer_petals": N_integer,
  "polygon_sides": N_or_0,
  "polygon_radius": number_or_0
}
All radii are scaled from 0 to 450 (for a 1000x1000 canvas with center at 500,500).
"""


# ── SVG Builder ─────────────────────────────────────────────────────────────

def build_svg_and_png(d: dict, style: str = "traditional") -> tuple[str, bytes]:
    """Converts a Gemini design spec into an SVG string and a 1024x1024 OpenCV PNG image."""
    cx, cy = 500, 500
    size = 1000
    
    # 1. Generate SVG
    svg_parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">']
    
    # Also prepare black-and-white OpenCV canvas for machine vectorization
    img = np.full((size, size, 3), 255, dtype=np.uint8)

    rings      = d.get("rings", [420, 290, 160])
    petals     = max(3, int(d.get("petals", 8)))
    inner_p    = max(3, int(d.get("inner_petals", petals)))
    outer_p    = max(3, int(d.get("outer_petals", petals)))
    poly_sides = int(d.get("polygon_sides", 0))
    poly_r     = float(d.get("polygon_radius", 0))

    # Outer Boundary Circle
    r_outer = float(rings[0]) if rings else 420
    cv2.circle(img, (cx, cy), int(r_outer), (0, 0, 0), 4)

    # Concentric rings
    for i, r in enumerate(rings):
        r_val = int(r)
        col = _pal(style, i)
        sw = 3 if i == 0 else 2
        svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_val}" fill="none" stroke="{col}" stroke-width="{sw}"/>')
        cv2.circle(img, (cx, cy), r_val, (0, 0, 0), 3)

    # Outer Petals
    petal_len = r_outer * 0.90
    ctrl_r    = petal_len * 0.30
    for i in range(outer_p):
        a = (i / outer_p) * 2 * math.pi
        a1 = a - math.pi / outer_p * 0.60
        a2 = a + math.pi / outer_p * 0.60
        tx, ty = _pt(cx, cy, petal_len, a)
        c1x, c1y = cx + ctrl_r * math.cos(a1) + (petal_len * 0.42) * math.cos(a), \
                   cy + ctrl_r * math.sin(a1) + (petal_len * 0.42) * math.sin(a)
        c2x, c2y = cx + ctrl_r * math.cos(a2) + (petal_len * 0.42) * math.cos(a), \
                   cy + ctrl_r * math.sin(a2) + (petal_len * 0.42) * math.sin(a)
        
        col = _pal(style, 0)
        svg_parts.append(
            f'<path d="M{cx},{cy} Q{c1x:.1f},{c1y:.1f} {tx:.1f},{ty:.1f} '
            f'Q{c2x:.1f},{c2y:.1f} {cx},{cy}Z" '
            f'fill="{col}1a" stroke="{col}" stroke-width="2"/>'
        )

        pts = np.array([
            [cx, cy],
            [int(c1x), int(c1y)],
            [int(tx), int(ty)],
            [int(c2x), int(c2y)],
        ], dtype=np.int32)
        cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 0), thickness=3)

    # Inner Petals
    if len(rings) > 1:
        inner_r2 = float(rings[1]) * 0.92
        for i in range(inner_p):
            a = ((i + 0.5) / inner_p) * 2 * math.pi
            a1 = a - math.pi / inner_p * 0.55
            a2 = a + math.pi / inner_p * 0.55
            tx, ty = _pt(cx, cy, inner_r2, a)
            cr = inner_r2 * 0.30
            c1x = cx + cr * math.cos(a1) + inner_r2 * 0.42 * math.cos(a)
            c1y = cy + cr * math.sin(a1) + inner_r2 * 0.42 * math.sin(a)
            c2x = cx + cr * math.cos(a2) + inner_r2 * 0.42 * math.cos(a)
            c2y = cy + cr * math.sin(a2) + inner_r2 * 0.42 * math.sin(a)
            
            col = _pal(style, 1)
            svg_parts.append(
                f'<path d="M{cx},{cy} Q{c1x:.1f},{c1y:.1f} {tx:.1f},{ty:.1f} '
                f'Q{c2x:.1f},{c2y:.1f} {cx},{cy}Z" '
                f'fill="{col}20" stroke="{col}" stroke-width="2"/>'
            )
            pts_in = np.array([
                [cx, cy],
                [int(c1x), int(c1y)],
                [int(tx), int(ty)],
                [int(c2x), int(c2y)],
            ], dtype=np.int32)
            cv2.polylines(img, [pts_in], isClosed=True, color=(0, 0, 0), thickness=3)

    # Polygons / Stars
    if poly_sides >= 3 and poly_r > 0:
        poly_pts = []
        for i in range(poly_sides):
            ang = (i / poly_sides) * 2 * math.pi
            px = int(cx + poly_r * math.cos(ang))
            py = int(cy + poly_r * math.sin(ang))
            poly_pts.append([px, py])
        
        pts_poly = np.array(poly_pts, dtype=np.int32)
        cv2.polylines(img, [pts_poly], isClosed=True, color=(0, 0, 0), thickness=3)
        pts_svg = " ".join(f"{p[0]},{p[1]}" for p in poly_pts)
        svg_parts.append(f'<polygon points="{pts_svg}" fill="none" stroke="{_pal(style, 2)}" stroke-width="2"/>')

    # Central Core Motif
    cv2.circle(img, (cx, cy), 35, (0, 0, 0), 3)
    cv2.circle(img, (cx, cy), 15, (0, 0, 0), -1)
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="35" fill="{_pal(style, 0)}55" stroke="{_pal(style, 0)}" stroke-width="2.5"/>')
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="15" fill="{_pal(style, 1)}"/>')
    svg_parts.append('</svg>')

    ok_enc, buf = cv2.imencode(".png", img)
    png_bytes = buf.tobytes() if ok_enc else b""
    return "".join(svg_parts), png_bytes


# ── Public Data Class ──────────────────────────────────────────────────────────

@dataclass
class GeminiImage:
    image_bytes: bytes
    mime_type: str
    caption: str
    svg: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    @property
    def data_url(self) -> str:
        b64 = base64.b64encode(self.image_bytes).decode("ascii")
        return f"data:{self.mime_type};base64,{b64}"


# ── Call Gemini AI via Google AI Studio API ──────────────────────────────────

async def call_gemini_structured(
    *, theme: str, symmetry: int, complexity: str, style: str, api_key: str, timeout: float = 25.0
) -> List[dict]:
    """Queries Gemini 2.0 / 1.5 on Google AI Studio for structured Pookalam designs."""
    user_prompt = (
        f"User Prompt / Cultural Theme: {theme}\n"
        f"Rotational Symmetry: {symmetry}-fold\n"
        f"Complexity: {complexity}\n"
        f"Design Style: {style}\n\n"
        f"Generate 3 unique, culturally meaningful Pookalam designs based on this theme. "
        f"Return ONLY the JSON array of 3 objects."
    )

    models_to_try = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp",
    ]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": GEMINI_SYSTEM_PROMPT + "\n\n" + user_prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.85,
                "responseMimeType": "application/json",
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    body = resp.json()
                    candidates = body.get("candidates") or []
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        if raw_text.startswith("```"):
                            raw_text = raw_text.strip("`").replace("json\n", "", 1).strip()
                        designs = json.loads(raw_text)
                        if isinstance(designs, list) and len(designs) > 0:
                            log.info("Successfully received %d designs from Gemini (%s)", len(designs), model)
                            return designs[:3]
        except Exception as exc:
            log.warning("Gemini model %s query error: %s", model, exc)

    return []


# ── Fallback Procedural Mandala Generator ─────────────────────────────────────

def generate_procedural_fallback(petal_count: int, layer_count: int, variant: int, free_text: str = "") -> dict:
    themes = [
        ("Lotus Harmony", "Classic Kerala lotus petals radiating in rotational harmony."),
        ("Onam Mandala", "Concentric geometric rings inspired by festive Onam pookalams."),
        ("Floral Star", "Interlocking symmetrical starburst and petal arcs."),
    ]
    name, desc = themes[variant % len(themes)]
    if free_text.strip():
        name = f"{free_text.strip().title()} Motif {variant + 1}"
        desc = f"Geometric pookalam pattern inspired by {free_text}."

    return {
        "name": name,
        "description": desc,
        "symmetry": f"{petal_count}-fold",
        "complexity": "medium",
        "motifs": ["lotus", "mandala", "star"],
        "rings": [420, 280, 160],
        "petals": petal_count,
        "inner_petals": petal_count,
        "outer_petals": petal_count,
        "polygon_sides": petal_count if variant == 2 else 0,
        "polygon_radius": 220 if variant == 2 else 0,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def provider_available() -> bool:
    return True

def current_provider_name() -> str:
    if os.environ.get(_GEMINI_KEY_ENV) or os.environ.get("AI_API_KEY"):
        return "Google Gemini (AI Studio)"
    return "AI Vector Engine"


async def generate_pookalam_images(
    *,
    petal_count: int,
    layer_count: int,
    color_count: int = 2,
    free_text: str = "",
    style: str = "traditional",
    n: int = 3,
    timeout: float = 30.0,
) -> List[GeminiImage]:
    """Generates n pookalam designs by querying Gemini and rendering sharp vector art."""
    api_key = os.environ.get(_GEMINI_KEY_ENV, "").strip() or os.environ.get("AI_API_KEY", "").strip()

    raw_designs = []
    if api_key:
        theme = free_text.strip() or "Traditional Kerala Lotus Onam Pookalam"
        raw_designs = await call_gemini_structured(
            theme=theme,
            symmetry=petal_count,
            complexity="medium" if layer_count == 2 else ("detailed" if layer_count > 2 else "simple"),
            style=style,
            api_key=api_key,
            timeout=timeout,
        )

    # Fallback to mathematical pookalam geometries if API key absent or empty
    if not raw_designs:
        raw_designs = [
            generate_procedural_fallback(petal_count, layer_count, i, free_text)
            for i in range(n)
        ]

    results: List[GeminiImage] = []
    for i, d in enumerate(raw_designs[:n]):
        svg_code, png_bytes = build_svg_and_png(d, style=style)
        if len(png_bytes) > 200:
            results.append(GeminiImage(
                image_bytes=png_bytes,
                mime_type="image/png",
                caption=d.get("name", f"Design {i+1}"),
                svg=svg_code,
                title=d.get("name", f"Design {i+1}"),
                description=d.get("description", "Pookalam design candidate."),
            ))

    return results
