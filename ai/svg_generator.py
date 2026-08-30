"""
ai/svg_generator.py — deterministic local SVG generator for Pookalam designs.

Produces three visually distinct rotationally-symmetric SVGs using only
path, circle, line, and polygon elements on a 1000×1000 canvas (center 500,500).
No raster images, no text, no gradients, no external resources.
"""
from __future__ import annotations
import math
from typing import List, Tuple

CX, CY = 500, 500   # canvas centre
W, H   = 1000, 1000 # canvas size

# ── Colour palettes keyed by style ────────────────────────────────────────────
PALETTES = {
    "traditional": ["#c8860a", "#2e7d32", "#7b1fa2", "#e65100"],
    "floral":      ["#e91e63", "#ff9800", "#4caf50", "#9c27b0"],
    "geometric":   ["#1565c0", "#00695c", "#f57f17", "#6a1b9a"],
    "modern":      ["#263238", "#00bcd4", "#ff5722", "#8bc34a"],
    "festival":    ["#d32f2f", "#f57c00", "#388e3c", "#7b1fa2"],
    "minimal":     ["#546e7a", "#90a4ae", "#b0bec5", "#78909c"],
}

def _palette(style: str) -> List[str]:
    return PALETTES.get(style, PALETTES["traditional"])


def _lotus_keyword(theme: str) -> bool:
    return any(w in theme.lower() for w in ["lotus", "padma", "lily", "flower"])

def _kerala_keyword(theme: str) -> bool:
    return any(w in theme.lower() for w in ["kerala", "onam", "thrissur", "traditional"])


# ── Low-level SVG helpers ─────────────────────────────────────────────────────

def _circle(cx: float, cy: float, r: float, stroke: str, sw: float = 1.5,
            fill: str = "none") -> str:
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:.2f}"/>')


def _petal(cx: float, cy: float, angle: float, length: float, width_ratio: float,
           stroke: str, fill: str = "none", sw: float = 1.5) -> str:
    """Quadratic-bezier petal centred at (cx,cy), pointing in direction angle."""
    tip_x = cx + length * math.cos(angle)
    tip_y = cy + length * math.sin(angle)
    side = angle + math.pi / 2
    ctrl_r = length * width_ratio
    c1x = cx + ctrl_r * math.cos(angle - math.pi / 6) + (length * 0.4) * math.cos(angle)
    c1y = cy + ctrl_r * math.sin(angle - math.pi / 6) + (length * 0.4) * math.sin(angle)
    c2x = cx + ctrl_r * math.cos(angle + math.pi / 6) + (length * 0.4) * math.cos(angle)
    c2y = cy + ctrl_r * math.sin(angle + math.pi / 6) + (length * 0.4) * math.sin(angle)
    return (f'<path d="M{cx:.2f},{cy:.2f} Q{c1x:.2f},{c1y:.2f} {tip_x:.2f},{tip_y:.2f} '
            f'Q{c2x:.2f},{c2y:.2f} {cx:.2f},{cy:.2f}Z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:.2f}"/>')


def _polygon_ring(cx: float, cy: float, r: float, n: int,
                  stroke: str, sw: float = 1.5, rotation: float = 0) -> str:
    pts = []
    for i in range(n):
        a = rotation + (i / n) * 2 * math.pi
        pts.append(f"{cx + r*math.cos(a):.2f},{cy + r*math.sin(a):.2f}")
    return (f'<polygon points="{" ".join(pts)}" '
            f'fill="none" stroke="{stroke}" stroke-width="{sw:.2f}"/>')


def _diamond_tick(cx: float, cy: float, r: float, angle: float,
                  size: float, stroke: str, sw: float = 1.2) -> str:
    """A small diamond accent at radius r along angle."""
    ix = cx + (r - size) * math.cos(angle)
    iy = cy + (r - size) * math.sin(angle)
    ox = cx + (r + size) * math.cos(angle)
    oy = cy + (r + size) * math.sin(angle)
    lx = cx + r * math.cos(angle - 0.08)
    ly = cy + r * math.sin(angle - 0.08)
    rx = cx + r * math.cos(angle + 0.08)
    ry = cy + r * math.sin(angle + 0.08)
    return (f'<path d="M{ix:.2f},{iy:.2f} L{lx:.2f},{ly:.2f} L{ox:.2f},{oy:.2f} '
            f'L{rx:.2f},{ry:.2f}Z" fill="none" stroke="{stroke}" stroke-width="{sw:.2f}"/>')


def _wrap_svg(inner: str) -> str:
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
            f'{inner}</svg>')


# ── Design 1 — Petal Ring (lotus-inspired) ────────────────────────────────────

def design_petal_ring(n: int, complexity: str, style: str, theme: str) -> str:
    cols = _palette(style)
    parts = []
    outer_r = 420

    # Boundary circle
    parts.append(_circle(CX, CY, outer_r, cols[0], 1.5))

    # Outer petals
    petal_len = 380 if _lotus_keyword(theme) else 340
    for i in range(n):
        a = (i / n) * 2 * math.pi
        parts.append(_petal(CX, CY, a, petal_len, 0.25, cols[0], fill=cols[0] + "18"))

    # Second petal ring (offset by half step) — medium & detailed only
    if complexity in ("medium", "detailed"):
        for i in range(n):
            a = ((i + 0.5) / n) * 2 * math.pi
            parts.append(_petal(CX, CY, a, petal_len * 0.6, 0.2, cols[1], fill=cols[1] + "14"))

    # Guide circles
    for r in [300, 200, 100]:
        parts.append(_circle(CX, CY, r, cols[2], 0.8))

    # Inner details for detailed
    if complexity == "detailed":
        for i in range(n * 2):
            a = (i / (n * 2)) * 2 * math.pi
            parts.append(_diamond_tick(CX, CY, 200, a, 12, cols[3]))

    # Centre
    parts.append(_circle(CX, CY, 40, cols[1], 2.0, fill=cols[1] + "44"))
    parts.append(_circle(CX, CY, 15, cols[0], 1.5, fill=cols[0]))
    return _wrap_svg("".join(parts))


# ── Design 2 — Mandala Rings (geometric / traditional) ───────────────────────

def design_mandala(n: int, complexity: str, style: str, theme: str) -> str:
    cols = _palette(style)
    parts = []

    rings = [420, 340, 260, 180] if complexity == "detailed" else (
            [420, 320, 200] if complexity == "medium" else [420, 280])

    for idx, r in enumerate(rings):
        parts.append(_circle(CX, CY, r, cols[idx % len(cols)], 1.8))
        # Diamond ticks at each symmetry point
        for i in range(n):
            a = (i / n) * 2 * math.pi
            parts.append(_diamond_tick(CX, CY, r, a, 18, cols[(idx + 1) % len(cols)]))

    # Polygon outline
    parts.append(_polygon_ring(CX, CY, 390, n, cols[1], 1.2))
    if complexity != "simple":
        parts.append(_polygon_ring(CX, CY, 390, n, cols[2], 0.8, rotation=math.pi / n))

    # Radial lines
    if complexity == "detailed" or _kerala_keyword(theme):
        for i in range(n):
            a = (i / n) * 2 * math.pi
            x2 = CX + 420 * math.cos(a)
            y2 = CY + 420 * math.sin(a)
            parts.append(f'<line x1="{CX}" y1="{CY}" x2="{x2:.2f}" y2="{y2:.2f}" '
                         f'stroke="{cols[0]}44" stroke-width="1"/>')

    parts.append(_circle(CX, CY, 50, cols[0], 2.0, fill=cols[0] + "55"))
    parts.append(_circle(CX, CY, 18, cols[1], 1.5, fill=cols[1]))
    return _wrap_svg("".join(parts))


# ── Design 3 — Star Burst (geometric star with petal overlay) ─────────────────

def design_star_burst(n: int, complexity: str, style: str, theme: str) -> str:
    cols = _palette(style)
    parts = []
    star_r = 400

    # Outer guide
    parts.append(_circle(CX, CY, star_r + 20, cols[0], 1.0))

    # Star polygon (two interlocked if n >= 6)
    parts.append(_polygon_ring(CX, CY, star_r, n, cols[1], 1.8))
    if n >= 6:
        parts.append(_polygon_ring(CX, CY, star_r, n, cols[2], 1.2, rotation=math.pi / n))

    # Petal overlay
    petal_n = n
    for i in range(petal_n):
        a = (i / petal_n) * 2 * math.pi
        parts.append(_petal(CX, CY, a, star_r * 0.8, 0.18, cols[0], fill=cols[0] + "12"))

    # Inner ring details
    inner_r = star_r * 0.45
    parts.append(_circle(CX, CY, inner_r, cols[3], 1.5))
    if complexity in ("medium", "detailed"):
        for i in range(n):
            a = (i / n) * 2 * math.pi + math.pi / n
            parts.append(_petal(CX, CY, a, inner_r * 0.8, 0.22, cols[2], fill=cols[2] + "18"))

    if complexity == "detailed":
        parts.append(_polygon_ring(CX, CY, inner_r * 0.55, n, cols[1], 1.0))
        for i in range(n * 2):
            a = (i / (n * 2)) * 2 * math.pi
            parts.append(_diamond_tick(CX, CY, inner_r * 0.55, a, 10, cols[0]))

    parts.append(_circle(CX, CY, 45, cols[2], 2.0, fill=cols[2] + "44"))
    parts.append(_circle(CX, CY, 16, cols[0], 1.5, fill=cols[0]))
    return _wrap_svg("".join(parts))


# ── Public API ────────────────────────────────────────────────────────────────

def generate_local_svgs(
    n: int, complexity: str, style: str, theme: str
) -> Tuple[str, str, str]:
    """
    Generate three deterministic Pookalam SVGs for the given parameters.
    Returns (svg1, svg2, svg3).
    Source is always local_fallback — no external calls are made.
    """
    d1 = design_petal_ring(n, complexity, style, theme)
    d2 = design_mandala(n, complexity, style, theme)
    d3 = design_star_burst(n, complexity, style, theme)
    return d1, d2, d3
