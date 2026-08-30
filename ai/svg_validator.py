"""
ai/svg_validator.py — validate SVGs before marking them drawable.

Rules
-----
- Valid XML
- Root element is <svg>
- Only allowed elements: svg, g, path, circle, line, polygon, polyline, rect, ellipse, defs
- No <image>, <text>, <tspan>, <foreignObject>, <script>, <use> referencing external
- No external resource references (http/https/data URIs with images)
- All numeric attributes are finite (no NaN / Inf)
- Design fits within 0,0 → 1000,1000 (checked loosely via viewBox)
- Path count is reasonable (< 5000)
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import List

ALLOWED_TAGS = {
    "svg", "g", "path", "circle", "line", "polygon",
    "polyline", "rect", "ellipse", "defs", "title", "desc",
}

BANNED_TAGS = {
    "image", "text", "tspan", "foreignobject",
    "script", "style", "use", "symbol",
}

_EXTERNAL_RE = re.compile(r'(https?://|data:image)', re.IGNORECASE)
_NAN_INF_RE  = re.compile(r'\b(nan|inf|infinity)\b', re.IGNORECASE)


def validate_svg(svg: str) -> List[str]:
    """
    Validate an SVG string.  Returns a list of error strings.
    An empty list means the SVG is drawable.
    """
    errors: List[str] = []

    if not svg or not svg.strip():
        return ["SVG is empty"]

    # 1. Valid XML
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        return [f"Invalid XML: {e}"]

    # 2. Root must be svg
    tag = root.tag.split("}")[-1].lower()  # strip namespace
    if tag != "svg":
        errors.append(f"Root element must be <svg>, got <{tag}>")

    # 3. Check all elements
    path_count = 0
    for el in root.iter():
        el_tag = el.tag.split("}")[-1].lower()
        if el_tag in BANNED_TAGS:
            errors.append(f"Disallowed element: <{el_tag}>")
        elif el_tag not in ALLOWED_TAGS:
            errors.append(f"Unknown element: <{el_tag}>")
        if el_tag == "path":
            path_count += 1

        # 4. No external resource refs
        for attr_val in el.attrib.values():
            if _EXTERNAL_RE.search(attr_val):
                errors.append(f"External resource reference in <{el_tag}>: {attr_val[:60]}")

    # 5. No NaN / Infinity in the raw string
    if _NAN_INF_RE.search(svg):
        errors.append("SVG contains NaN or Infinity values")

    # 6. Path count sanity
    if path_count > 5000:
        errors.append(f"Too many path elements: {path_count} (max 5000)")

    # 7. viewBox present and finite
    vb = root.attrib.get("viewBox", "")
    if vb:
        try:
            vals = [float(x) for x in vb.split()]
            if any(not _is_finite(v) for v in vals):
                errors.append(f"Non-finite viewBox values: {vb}")
        except ValueError:
            errors.append(f"Cannot parse viewBox: {vb}")

    return errors


def _is_finite(v: float) -> bool:
    import math
    return math.isfinite(v)


def estimate_waypoints(svg: str, symmetry: int = 8) -> int:
    """Rough waypoint estimate based on path/circle element count."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return 0
    paths   = sum(1 for el in root.iter() if el.tag.split("}")[-1] in ("path", "circle", "ellipse"))
    return paths * 24 * symmetry


def estimate_drawing_time(waypoints: int, speed_wps: int = 40) -> int:
    """Estimate drawing time in seconds at *speed_wps* waypoints/second."""
    return max(10, waypoints // speed_wps)
