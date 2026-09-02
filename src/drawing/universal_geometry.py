"""Phase 20 — Universal Geometric Representation & Parameter Provenance Schema.

Provides generic geometric entity representations, dimensional entities,
feature cues, mathematical parameter provenance, and truth-preserving status models.
ZERO part-specific names, zero semantic shape classifications in geometric decisions.
"""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional, Tuple, Union
from src.drawing.compat import BaseModel, Field, field_validator


class UniversalStatus(str, enum.Enum):
    """Truth-preserving reconstruction lifecycle and constraint statuses."""
    PROCESSING = "PROCESSING"
    CONSTRAINED = "CONSTRAINED"
    PARTIALLY_CONSTRAINED = "PARTIALLY_CONSTRAINED"
    AMBIGUOUS = "AMBIGUOUS"
    CANDIDATE_GENERATED = "CANDIDATE_GENERATED"
    CANDIDATE_VALIDATING = "CANDIDATE_VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    COMPLETE = "COMPLETE"


class GenericGeometryType(str, enum.Enum):
    """Primitive 2D/3D geometric entity types extracted from drawing views."""
    POINT = "POINT"
    LINE = "LINE"
    ARC = "ARC"
    CIRCLE = "CIRCLE"
    ELLIPSE = "ELLIPSE"
    SPLINE = "SPLINE"
    POLYLINE = "POLYLINE"
    CLOSED_PROFILE = "CLOSED_PROFILE"
    OPEN_PROFILE = "OPEN_PROFILE"
    CENTERLINE = "CENTERLINE"
    SYMMETRY_AXIS = "SYMMETRY_AXIS"
    SECTION_LINE = "SECTION_LINE"
    HIDDEN_LINE = "HIDDEN_LINE"
    DIMENSION_LINE = "DIMENSION_LINE"
    LEADER_LINE = "LEADER_LINE"


class GenericDimensionType(str, enum.Enum):
    """Dimensional constraint types extracted from engineering callouts."""
    LINEAR_DIMENSION = "LINEAR_DIMENSION"
    DIAMETER_DIMENSION = "DIAMETER_DIMENSION"
    RADIUS_DIMENSION = "RADIUS_DIMENSION"
    ANGULAR_DIMENSION = "ANGULAR_DIMENSION"
    DEPTH_DIMENSION = "DEPTH_DIMENSION"
    COUNT_DIMENSION = "COUNT_DIMENSION"
    THREAD_DIMENSION = "THREAD_DIMENSION"
    CHAMFER_DIMENSION = "CHAMFER_DIMENSION"
    TOLERANCE_DIMENSION = "TOLERANCE_DIMENSION"


class FeatureCueType(str, enum.Enum):
    """Syntactic feature cues indicated by drawing symbols or geometry patterns."""
    HOLE = "HOLE"
    SLOT = "SLOT"
    COUNTERBORE = "COUNTERBORE"
    COUNTERSINK = "COUNTERSINK"
    THREAD = "THREAD"
    ROTATIONAL_PATTERN = "ROTATIONAL_PATTERN"
    LINEAR_PATTERN = "LINEAR_PATTERN"
    FILLET = "FILLET"
    CHAMFER = "CHAMFER"
    POCKET = "POCKET"
    BOSS = "BOSS"


class ParameterProvenance(BaseModel):
    """Uncompromising evidence provenance for a geometric parameter."""
    source_view_id: str
    source_dimension_id: Optional[str] = None
    raw_text: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    is_derived: bool = False
    derivation_rule: Optional[str] = None
    is_assumed: bool = False
    assumption_rationale: Optional[str] = None


class SolvedParameter(BaseModel):
    """A mathematically derived or explicitly proven CAD parameter."""
    parameter_id: str
    name: str
    value: Union[float, int, str, List[float], List[Tuple[float, float, float]], List[List[float]]]
    unit: str = "mm"
    provenance: List[ParameterProvenance] = Field(default_factory=list)
    derivation: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    constraint_dependencies: List[str] = Field(default_factory=list)

    def assert_proven(self) -> None:
        """Enforces that this parameter has explicit evidence provenance or valid derivation."""
        if not self.provenance:
            raise ValueError(f"Parameter '{self.name}' ({self.parameter_id}) has zero evidence provenance.")
        for prov in self.provenance:
            if prov.is_assumed and not prov.assumption_rationale:
                raise ValueError(f"Parameter '{self.name}' has ungrounded assumption without rationale.")


class GenericEntity(BaseModel):
    """Universal 2D/3D geometric entity representation with source evidence tracing."""
    entity_id: str
    geometry_type: GenericGeometryType
    source_view_id: str
    source_coordinates: List[Tuple[float, float]] = Field(default_factory=list)  # (u, v) in view frame
    spatial_coordinates_3d: List[Tuple[float, float, float]] = Field(default_factory=list)  # (x, y, z) in CAD
    is_closed: bool = False
    radius_or_diameter: Optional[float] = None
    center_point: Optional[Tuple[float, float]] = None
    axis_direction: Optional[Tuple[float, float, float]] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    associated_dimension_ids: List[str] = Field(default_factory=list)
    feature_cues: List[FeatureCueType] = Field(default_factory=list)


class GenericDimension(BaseModel):
    """Universal engineering dimension extracted from drawing annotations."""
    dimension_id: str
    dimension_type: GenericDimensionType
    source_view_id: str
    raw_text: str
    nominal_value: float
    tolerance_upper: float = 0.0
    tolerance_lower: float = 0.0
    unit: str = "mm"
    measured_axis: Optional[str] = None  # "X", "Y", "Z", "RADIAL", "ANGULAR"
    associated_entity_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
