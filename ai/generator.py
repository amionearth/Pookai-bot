"""
ai/generator.py — top-level Pookalam design generator.

Pipeline
--------
1. Try Gemini (parallel) via ai.gemini_client. N candidate images.
2. Validate each image (basic checks: decodable, not all-white, non-trivial).
   Candidates that fail validation are dropped here — per the web app spec,
   a bad design should never even be shown as a selectable option.
3. Wrap each surviving image in a DesignCandidate with a title + description.
4. If no API key is configured, raise a clear error so the route layer
   can return a 503 to the frontend.

Titles / descriptions are deterministic per slot so the user can compare
apples-to-apples across different prompt runs.
"""
from __future__ import annotations

import base64
import io
import logging
import uuid
from typing import List, Tuple

from .gemini_client import (
    generate_pookalam_images,
    provider_available,
    current_provider_name,
    GeminiImage,
)
from .models import DesignCandidate, DesignRequest

log = logging.getLogger(__name__)


# Three named slots so the candidates feel like a curated set, not 3 random rolls
_SLOT_META = [
    ("Petal Ring",  "Lotus-petal ring radiating from a central disc — a classic Onam motif."),
    ("Mandala",     "Layered mandala rings with diamond accents drawn in rotational symmetry."),
    ("Star Burst",  "Geometric star with overlapping petal arcs — bold and precise."),
]


# ── Image validation ──────────────────────────────────────────────────────────
#
# Per the web app spec: "If a generated design fails validation, don't show
# it as a selectable candidate at all." This is a *light* check — the heavy
# CV validation (vectorize endpoint) happens later, in the dedicated route.
# Here we just make sure the image is structurally usable.

def _validate_image(img: GeminiImage) -> Tuple[bool, List[str]]:
    """
    Quick sanity check on a freshly-generated image. Returns (ok, errors).
    Heavy CV happens later in the vectorize endpoint.
    """
    errors: List[str] = []
    if not img.image_bytes or len(img.image_bytes) < 200:
        errors.append("Image is empty or suspiciously small.")
        return False, errors
    if img.mime_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        errors.append(f"Unsupported mime type: {img.mime_type!r}.")
        return False, errors

    # Try to decode via PIL if it's available — gives us cheap structural
    # checks (real dimensions, not all-white, not corrupted). Falls back to
    # a no-op pass if PIL is missing, since this is a soft check.
    try:
        from PIL import Image
    except ImportError:
        return True, []

    try:
        with Image.open(io.BytesIO(img.image_bytes)) as pil:
            pil.verify()  # detects corruption
        with Image.open(io.BytesIO(img.image_bytes)) as pil:
            w, h = pil.size
            if w < 128 or h < 128:
                errors.append(f"Image too small: {w}x{h}.")
                return False, errors
            # Convert to grayscale and check that it isn't a blank canvas
            gray = pil.convert("L")
            extrema = gray.getextrema()
            if extrema[1] - extrema[0] < 32:
                errors.append(
                    "Image looks blank or near-uniform (no contrast). "
                    "Gemini may have failed to render the design."
                )
                return False, errors
    except Exception as exc:
        errors.append(f"Image failed to decode: {exc}")
        return False, errors

    return True, []


# ── Public API ────────────────────────────────────────────────────────────────

def ai_available() -> bool:
    """True if the currently-configured image provider is usable right now."""
    return provider_available()


async def generate_designs_async(
    request: DesignRequest, n: int = 3,
) -> List[DesignCandidate]:
    """
    Async entry point — fires the n Gemini calls in parallel and returns
    DesignCandidate objects (with base64-encoded images). Candidates that
    fail validation are silently dropped.
    """
    images = await generate_pookalam_images(
        petal_count=request.petal_count,
        layer_count=request.layer_count,
        color_count=request.color_count,
        free_text=request.free_text,
        style=request.style or "traditional",
        n=n,
    )

    candidates: List[DesignCandidate] = []
    for i, img in enumerate(images):
        ok, errors = _validate_image(img)
        if not ok:
            log.warning("Dropping candidate %d: %s", i, "; ".join(errors))
            continue
        title = img.title if img.title else (_SLOT_META[i][0] if i < len(_SLOT_META) else f"Design {i + 1}")
        desc  = img.description if img.description else (_SLOT_META[i][1] if i < len(_SLOT_META) else "Pookalam design candidate.")
        candidates.append(DesignCandidate(
            id=str(uuid.uuid4()),
            title=title,
            description=desc,
            petal_count=request.petal_count,
            layer_count=request.layer_count,
            color_count=request.color_count,
            free_text=request.free_text,
            image_b64=base64.b64encode(img.image_bytes).decode("ascii"),
            image_mime=img.mime_type,
            drawable=True,
            source="gemini",
        ))

    if not candidates and images:
        log.warning(
            "All %d Gemini images failed validation for petal=%d layer=%d color=%d",
            len(images), request.petal_count, request.layer_count, request.color_count,
        )
    elif not candidates:
        log.warning("Gemini returned no images.")
    return candidates
