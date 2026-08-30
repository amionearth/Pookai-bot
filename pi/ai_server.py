"""
pi/ai_server.py — PookalBot AI Design Server

Serves the frontend AND the Gemini-powered design generation API on the
same origin so there are zero CORS issues.

Start:
    set GEMINI_API_KEY=your-key-here          # Windows CMD
    $env:GEMINI_API_KEY="your-key-here"       # Windows PowerShell
    python pi/ai_server.py

Frontend: http://localhost:5000
API docs: http://localhost:5000/api/generate-design  (POST)
"""

import json
import math
import os
import sys
import uuid
import logging
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("ai_server")

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.6-flash:generateContent"
)

# ── SVG builder ────────────────────────────────────────────────────────────────

PALETTES = {
    "traditional": ["#c8860a", "#2e7d32", "#7b1fa2", "#e65100"],
    "floral":      ["#e91e63", "#ff9800", "#4caf50", "#9c27b0"],
    "geometric":   ["#1565c0", "#00695c", "#f57f17", "#6a1b9a"],
    "modern":      ["#37474f", "#00acc1", "#ff7043", "#66bb6a"],
    "festival":    ["#d32f2f", "#f57c00", "#388e3c", "#7b1fa2"],
    "minimal":     ["#78909c", "#90a4ae", "#a1887f", "#80cbc4"],
}

def _pal(style: str, idx: int) -> str:
    cols = PALETTES.get(style, PALETTES["traditional"])
    return cols[idx % len(cols)]

def _pt(cx, cy, r, angle):
    return cx + r * math.cos(angle), cy + r * math.sin(angle)

def build_svg(d: dict, style: str) -> str:
    """Convert a Gemini design spec dict into a drawable SVG string."""
    cx, cy = 500, 500
    parts = [f'<svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg">']

    rings      = d.get("rings", [400, 280, 160])
    petals     = max(2, int(d.get("petals", 8)))
    inner_p    = max(2, int(d.get("inner_petals", petals)))
    outer_p    = max(2, int(d.get("outer_petals", petals)))
    poly_sides = int(d.get("polygon_sides", 0))
    poly_r     = float(d.get("polygon_radius", 0))

    # Boundary + guide rings
    for i, r in enumerate(rings):
        r = float(r)
        col = _pal(style, i)
        sw  = 2.5 if i == 0 else 1.5
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="{sw}"/>')

    # Outer petals
    outer_r = float(rings[0]) if rings else 400
    petal_len = outer_r * 0.88
    ctrl_r    = petal_len * 0.28
    for i in range(outer_p):
        a  = (i / outer_p) * 2 * math.pi
        a1 = a - math.pi / outer_p * 0.55
        a2 = a + math.pi / outer_p * 0.55
        tx, ty   = _pt(cx, cy, petal_len, a)
        c1x, c1y = cx + ctrl_r * math.cos(a1) + (petal_len * 0.42) * math.cos(a), \
                   cy + ctrl_r * math.sin(a1) + (petal_len * 0.42) * math.sin(a)
        c2x, c2y = cx + ctrl_r * math.cos(a2) + (petal_len * 0.42) * math.cos(a), \
                   cy + ctrl_r * math.sin(a2) + (petal_len * 0.42) * math.sin(a)
        col  = _pal(style, 0)
        parts.append(
            f'<path d="M{cx},{cy} Q{c1x:.1f},{c1y:.1f} {tx:.1f},{ty:.1f} '
            f'Q{c2x:.1f},{c2y:.1f} {cx},{cy}Z" '
            f'fill="{col}1a" stroke="{col}" stroke-width="1.8"/>'
        )

    # Inner petals (offset half-step)
    if len(rings) > 1:
        inner_r2 = float(rings[1]) * 0.9
        for i in range(inner_p):
            a  = ((i + 0.5) / inner_p) * 2 * math.pi
            a1 = a - math.pi / inner_p * 0.5
            a2 = a + math.pi / inner_p * 0.5
            tx, ty   = _pt(cx, cy, inner_r2, a)
            cr = inner_r2 * 0.28
            c1x = cx + cr * math.cos(a1) + inner_r2 * 0.42 * math.cos(a)
            c1y = cy + cr * math.sin(a1) + inner_r2 * 0.42 * math.sin(a)
            c2x = cx + cr * math.cos(a2) + inner_r2 * 0.42 * math.cos(a)
            c2y = cy + cr * math.sin(a2) + inner_r2 * 0.42 * math.sin(a)
            col = _pal(style, 1)
            parts.append(
                f'<path d="M{cx},{cy} Q{c1x:.1f},{c1y:.1f} {tx:.1f},{ty:.1f} '
                f'Q{c2x:.1f},{c2y:.1f} {cx},{cy}Z" '
                f'fill="{col}15" stroke="{col}" stroke-width="1.4"/>'
            )

    # Optional polygon
    if poly_sides >= 3 and poly_r > 0:
        pts = " ".join(
            f"{cx + poly_r * math.cos((i/poly_sides)*2*math.pi):.1f},"
            f"{cy + poly_r * math.sin((i/poly_sides)*2*math.pi):.1f}"
            for i in range(poly_sides)
        )
        col = _pal(style, 2)
        parts.append(f'<polygon points="{pts}" fill="none" stroke="{col}" stroke-width="1.6"/>')
        # Second polygon rotated
        pts2 = " ".join(
            f"{cx + poly_r * math.cos((i/poly_sides)*2*math.pi + math.pi/poly_sides):.1f},"
            f"{cy + poly_r * math.sin((i/poly_sides)*2*math.pi + math.pi/poly_sides):.1f}"
            for i in range(poly_sides)
        )
        col2 = _pal(style, 3)
        parts.append(f'<polygon points="{pts2}" fill="none" stroke="{col2}" stroke-width="1.2"/>')

    # Radial tick marks on second ring
    if len(rings) > 1:
        r2  = float(rings[1])
        col = _pal(style, 3)
        tick_n = petals * 2
        for i in range(tick_n):
            a   = (i / tick_n) * 2 * math.pi
            ix  = cx + (r2 - 14) * math.cos(a)
            iy  = cy + (r2 - 14) * math.sin(a)
            ox  = cx + (r2 + 14) * math.cos(a)
            oy  = cy + (r2 + 14) * math.sin(a)
            lx  = cx + r2 * math.cos(a - 0.09)
            ly  = cy + r2 * math.sin(a - 0.09)
            rx2 = cx + r2 * math.cos(a + 0.09)
            ry2 = cy + r2 * math.sin(a + 0.09)
            parts.append(
                f'<path d="M{ix:.1f},{iy:.1f} L{lx:.1f},{ly:.1f} '
                f'L{ox:.1f},{oy:.1f} L{rx2:.1f},{ry2:.1f}Z" '
                f'fill="none" stroke="{col}" stroke-width="1.1"/>'
            )

    # Centre
    col0 = _pal(style, 0)
    col1 = _pal(style, 1)
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="30" fill="{col0}55" stroke="{col0}" stroke-width="2"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="12" fill="{col1}"/>') 

    parts.append('</svg>')
    return "".join(parts)


# ── Gemini call ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert in traditional Kerala Pookalam (floral rangoli) art and geometry.
Your job is to describe THREE mathematically distinct Pookalam designs in structured JSON.

IMPORTANT RULES:
- Each design MUST be genuinely different — different structure, different motif concept
- Designs must reflect the user's theme (e.g. Mahabali, Kathakali, Vallam Kali, Thiruvathira, Onam)
- Use mathematical geometry: concentric rings, radial petals, polygons, stars
- All values must be numeric and robot-drawable
- Do NOT return raster images, free-form art, or text descriptions of colors
- Do NOT return generic "lotus" designs unless the theme specifically calls for lotus

Return ONLY a valid JSON array with exactly 3 objects. No markdown, no code fences, no extra text.

Each object must have:
{
  "name": "short design name (max 4 words)",
  "description": "one sentence about this design's cultural connection",
  "symmetry": "N-fold",
  "complexity": "simple|medium|detailed",
  "motifs": ["list", "of", "motif", "keywords"],
  "rings": [outer_radius, mid_radius, inner_radius],
  "petals": N,
  "inner_petals": N,
  "outer_petals": N,
  "polygon_sides": N_or_0,
  "polygon_radius": number_or_0
}

All radii are out of a 500-unit canvas radius (0–490).
"""

def call_gemini(theme: str, symmetry: str, complexity: str, style: str) -> list:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    user_prompt = (
        f"Theme: {theme}\n"
        f"Symmetry: {symmetry}\n"
        f"Complexity: {complexity}\n"
        f"Style: {style}\n\n"
        f"Generate 3 unique Pookalam designs for this theme. "
        f"Make them culturally meaningful and geometrically distinct. "
        f"Return ONLY a JSON array, no markdown, no explanation."
    )

    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    payload = json.dumps({
        "contents": [{
            "parts": [{"text": full_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.9,
            "responseMimeType": "application/json",
        }
    }).encode("utf-8")

    url = f"{GEMINI_API_URL}?key={api_key}"
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    raw_text = body["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown fences if present despite responseMimeType
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:])
        raw_text = raw_text.rstrip("`").strip()

    designs = json.loads(raw_text)
    if not isinstance(designs, list):
        raise ValueError(f"Gemini returned non-list JSON: {type(designs)}")
    return designs[:3]


# ── HTTP handler ───────────────────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    """Serves static files from web/static AND handles /api/* endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        log.info(fmt % args)

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/generate-design":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "Invalid JSON body"})
            return

        theme      = str(body.get("theme", "")).strip()
        symmetry   = str(body.get("symmetry", "8-fold")).strip()
        complexity = str(body.get("complexity", "simple")).strip()
        style      = str(body.get("style", "traditional")).strip()

        if not theme:
            self._json(400, {"ok": False, "error": "Theme is required"})
            return

        log.info("Generating designs — theme=%r sym=%s cplx=%s style=%s",
                 theme, symmetry, complexity, style)

        # Check API key early — give a clear error
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            self._json(503, {
                "ok": False,
                "error": "GEMINI_API_KEY is not set on the server. "
                         "Get a key at https://aistudio.google.com/apikey and restart."
            })
            return

        try:
            raw_designs = call_gemini(theme, symmetry, complexity, style)
        except HTTPError as e:
            body_txt = e.read().decode("utf-8", errors="replace")
            log.error("Gemini HTTP %d: %s", e.code, body_txt)
            self._json(502, {"ok": False, "error": f"Gemini API error {e.code}: {body_txt[:200]}"})
            return
        except URLError as e:
            log.error("Network error: %s", e)
            self._json(502, {"ok": False, "error": f"Network error: {e.reason}"})
            return
        except ValueError as e:
            log.error("Gemini response error: %s", e)
            self._json(502, {"ok": False, "error": str(e)})
            return
        except Exception as e:
            log.exception("Unexpected error")
            self._json(500, {"ok": False, "error": f"Server error: {e}"})
            return

        if not raw_designs:
            self._json(502, {"ok": False, "error": "Gemini returned 0 designs"})
            return

        results = []
        for d in raw_designs:
            svg = build_svg(d, style)
            results.append({
                "id":          str(uuid.uuid4()),
                "name":        d.get("name", "Design"),
                "description": d.get("description", ""),
                "symmetry":    d.get("symmetry", symmetry),
                "complexity":  d.get("complexity", complexity),
                "motifs":      d.get("motifs", []),
                "svg":         svg,
            })

        self._json(200, {"ok": True, "designs": results})

    def do_GET(self):
        # Strip /static/ prefix if present so files in STATIC_DIR resolve properly
        if self.path.startswith("/static/"):
            self.path = self.path[len("/static"):]

        # Health check
        if self.path == "/api/health":
            has_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
            self._json(200, {
                "status": "ok",
                "ai_available": has_key,
                "mode": "gemini" if has_key else "no_key",
            })
            return
        # Serve static files for everything else
        super().do_GET()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    key  = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        log.warning("=" * 60)
        log.warning("  GEMINI_API_KEY is not set!")
        log.warning("  Get a FREE key at: https://aistudio.google.com/apikey")
        log.warning("  Then run:")
        log.warning("  PowerShell: $env:GEMINI_API_KEY='AIzaSy...'")
        log.warning("  CMD:        set GEMINI_API_KEY=AIzaSy...")
        log.warning("=" * 60)
    else:
        masked = key[:6] + "..." + key[-4:]
        log.info("✓  API key loaded: %s", masked)
    log.info("PookalBot AI Server → http://localhost:%d", port)
    log.info("Static files from:  %s", STATIC_DIR)
    server = HTTPServer(("", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
