"""
ai/models.py — shared Pydantic models for the AI design generation layer.

Designs are raster images (PNG/JPEG) returned by Gemini — not inline SVG.
The base64-encoded image is what flows through the system; the server
turns it into a `data:` URL for the frontend.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# The three controls from Step 1 of the web app spec — mapped to specific
# numeric ranges. Defaults are 6 / 3 / 2 (6-fold symmetry is the most
# common real pookalam; 3 colors + 2 rings is a balanced, drawable middle).
PetalCount  = Literal[4, 5, 6, 8, 10, 12]
ColorCount  = Literal[2, 3, 4, 5]
LayerCount  = Literal[1, 2, 3]


class DesignRequest(BaseModel):
    """
    What the user tells the AI about the design they want.

    The developer system prompt (server-side, never sent to the user) is what
    actually constrains the image to be drawable. The fields here describe
    *what* the user wants, not *how* the image has to look.
    """
    petal_count:  PetalCount = Field(6,
        description="Rotational symmetry — number of petals/points around the centre.")
    layer_count:  LayerCount = Field(2,
        description="Concentric rings/layers from the centre outward (1-3).")
    color_count:  ColorCount = Field(3,
        description="Number of distinct colors in the design (2-5).")
    free_text:    str = Field("", max_length=500,
        description="Optional additional description from the user.")
    style:        Optional[str] = Field("traditional", description="Art aesthetic palette")


class DesignCandidate(BaseModel):
    """A single Pookalam design — a Gemini-generated raster image."""
    id: str
    title: str
    description: str
    petal_count: int
    layer_count: int
    color_count: int
    free_text:   str = ""

    # The image itself (base64-encoded, mime-tagged)
    image_b64: str
    image_mime: str = "image/png"

    drawable: bool                  = True   # passed image validation
    validation_errors: List[str]    = []
    estimated_waypoints: int        = 0      # populated after vectorize
    estimated_drawing_time_sec: int = 0
    source: str                     = "gemini"  # "gemini" | "stub"
