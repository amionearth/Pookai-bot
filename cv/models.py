"""
models.py — shared dataclasses for the PookalBot CV pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class CircleResult:
    """Result of Hough circle detection."""
    center_x: float
    center_y: float
    radius: float
    confidence: float  # 0.0 – 1.0


@dataclass
class PolarRepresentation:
    """Unwrapped polar image and its coordinate mapping."""
    image: np.ndarray          # shape (r_bins, theta_bins)
    theta_bins: int
    r_bins: int
    center_x: float
    center_y: float
    radius_px: float


@dataclass
class SymmetryResult:
    """Result of rotational symmetry detection."""
    order: int              # e.g. 8 means 8-fold (45° period)
    confidence: float       # 0.0 – 1.0
    angular_period_rad: float


@dataclass
class Waypoint:
    """A single polar-plotter waypoint."""
    theta: float   # radians, [0, 2π)
    r: float       # normalised [0, 1]
    pen: int       # 1 = chalk down, 0 = chalk up


@dataclass
class PathPlan:
    """Complete output of the path-generation stage."""
    waypoints: List[Waypoint]
    center_x: float
    center_y: float
    radius_px: float
    symmetry_order: int

    def to_dict(self) -> dict:
        import math
        return {
            "version": 1,
            "coordinate_system": {
                "theta": "radians",
                "theta_range": [0, round(2 * math.pi, 6)],
                "r_range": [0, 1],
            },
            "center": {"x": round(self.center_x, 2), "y": round(self.center_y, 2)},
            "radius_px": round(self.radius_px, 2),
            "symmetry_order": self.symmetry_order,
            "waypoints": [
                {"theta": round(w.theta, 6), "r": round(w.r, 6), "pen": w.pen}
                for w in self.waypoints
            ],
        }


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class ValidationResult:
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
