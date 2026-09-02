"""Phase 1 — Global manufacturing constraint definitions and defaults.

Defines the constraint thresholds used by Phase 19B's post-execution
validation (via ConstraintAnalyzer) and by Phase 1 complete_dimensioning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GlobalConstraints:
    """Manufacturing and design constraint thresholds.

    These thresholds are checked after CAD reconstruction (Phase 19B) to
    ensure the reconstructed geometry meets minimum quality standards.
    """

    minimum_wall_thickness_mm: Optional[float] = 0.5
    """Minimum wall thickness in millimeters. None or 0.0 to skip."""

    minimum_feature_size_mm: Optional[float] = 0.1
    """Minimum feature (hole, slot, boss) size in millimeters."""

    minimum_face_radius_mm: Optional[float] = 0.05
    """Minimum fillet/chamfer radius in millimeters."""

    maximum_hole_ratio: Optional[float] = None
    """Maximum hole-to-material ratio (0.0-1.0). None to skip."""

    minimum_material_volume_mm3: Optional[float] = 0.01
    """Minimum solid volume in mm³ — catches degenerate solids."""

    maximum_aspect_ratio: Optional[float] = 10.0
    """Maximum feature aspect ratio (length/width). None to skip."""


@dataclass
class ConstraintCheckResult:
    """Result of checking a single constraint against a solid."""
    constraint_name: str
    passed: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    message: str = ""


# Predefined constraint sets for common material types
DEFAULT_CONSTRAINTS = GlobalConstraints(
    minimum_wall_thickness_mm=0.5,
    minimum_feature_size_mm=0.1,
    minimum_face_radius_mm=0.05,
    minimum_material_volume_mm3=0.01,
    maximum_aspect_ratio=10.0,
)

PLASTIC_CONSTRAINTS = GlobalConstraints(
    minimum_wall_thickness_mm=0.8,
    minimum_feature_size_mm=0.2,
    minimum_face_radius_mm=0.1,
    minimum_material_volume_mm3=1.0,
    maximum_aspect_ratio=8.0,
)

METAL_CASTING_CONSTRAINTS = GlobalConstraints(
    minimum_wall_thickness_mm=1.5,
    minimum_feature_size_mm=0.5,
    minimum_face_radius_mm=0.3,
    minimum_material_volume_mm3=10.0,
    maximum_aspect_ratio=6.0,
)

RAPID_PROTOTYPING_CONSTRAINTS = GlobalConstraints(
    minimum_wall_thickness_mm=1.0,
    minimum_feature_size_mm=0.3,
    minimum_face_radius_mm=0.2,
    minimum_material_volume_mm3=5.0,
    maximum_aspect_ratio=20.0,
)
