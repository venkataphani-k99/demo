"""Phase 17 — Pydantic schemas for 2D Engineering Drawing Understanding (UC2).

No CAD geometry is generated here. All structures represent visual/textual
understanding of the drawing image only.
"""
from __future__ import annotations

import enum
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from src.drawing.compat import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ViewType(str, enum.Enum):
    FRONT = "FRONT"
    TOP = "TOP"
    BOTTOM = "BOTTOM"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    REAR = "REAR"
    ISOMETRIC = "ISOMETRIC"
    SECTION = "SECTION"
    DETAIL = "DETAIL"
    AUXILIARY = "AUXILIARY"
    UNKNOWN = "UNKNOWN"


class DimensionType(str, enum.Enum):
    LINEAR = "linear"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    ALIGNED = "aligned"
    DIAMETER = "diameter"
    RADIUS = "radius"
    ANGLE = "angle"
    DEPTH = "depth"
    CHAMFER = "chamfer"
    THREAD = "thread"
    UNKNOWN = "unknown"


class EntityType(str, enum.Enum):
    STRAIGHT_EDGE = "straight_edge"
    LINE = "line"
    CIRCLE = "circle"
    ARC = "arc"
    ELLIPSE = "ellipse"
    SPLINE = "spline"
    POLYLINE = "polyline"
    CLOSED_PROFILE = "closed_profile"
    CENTERLINE = "centerline"
    CENTER_MARK = "center_mark"
    HIDDEN_LINE = "hidden_line"
    EXTENSION_LINE = "extension_line"
    DIMENSION_LINE = "dimension_line"
    ARROWHEAD = "arrowhead"
    SECTION_HATCH = "section_hatch"
    DATUM_SYMBOL = "datum_symbol"
    GD_T_FRAME = "gdt_frame"
    SURFACE_FINISH = "surface_finish"
    NOTE = "note"
    TITLE_BLOCK = "title_block"
    UNKNOWN = "unknown"


class CurveType(str, enum.Enum):
    LINE = "line"
    ARC = "arc"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    SPLINE = "spline"
    POLYLINE = "polyline"
    CLOSED_PROFILE = "closed_profile"


class ProfileCurve(BaseModel):
    """Detailed geometric curve or boundary segment of a physical feature."""
    curve_id: str
    curve_type: CurveType
    source_view: Optional[str] = None
    start_point: Optional[List[float]] = None     # [u, v] or [x, y, z]
    end_point: Optional[List[float]] = None       # [u, v] or [x, y, z]
    center_point: Optional[List[float]] = None    # [u, v] or [x, y, z]
    radius: Optional[float] = None
    major_radius: Optional[float] = None
    minor_radius: Optional[float] = None
    control_points: List[List[float]] = Field(default_factory=list)
    polyline_points: List[List[float]] = Field(default_factory=list)
    is_closed: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: str = ""



class ConsensusState(str, enum.Enum):
    AGREED = "agreed"
    DISAGREED = "disagreed"
    UNRESOLVED = "unresolved"
    CLAUDE_ONLY = "claude_only"
    GEMINI_ONLY = "gemini_only"


# ---------------------------------------------------------------------------
# Bounding box helper
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """Image-coordinate bounding box [x1, y1, x2, y2] in pixels."""
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def check_valid(cls, values):
        if isinstance(values, dict):
            x1, y1 = values.get("x1"), values.get("y1")
            x2, y2 = values.get("x2"), values.get("y2")
            if x1 is not None and x2 is not None and x2 <= x1:
                raise ValueError(f"Invalid bounding box: x2 ({x2}) must be > x1 ({x1})")
            if y1 is not None and y2 is not None and y2 <= y1:
                raise ValueError(f"Invalid bounding box: y2 ({y2}) must be > y1 ({y1})")
        elif hasattr(values, "x1"):
            if values.x2 <= values.x1 or values.y2 <= values.y1:
                raise ValueError(f"Invalid bounding box: x2 ({values.x2}) must be > x1 ({values.x1})")
        return values

    def as_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]


# ---------------------------------------------------------------------------
# Source metadata
# ---------------------------------------------------------------------------

class DrawingSource(BaseModel):
    """Immutable record of the uploaded drawing source file."""
    filename: str
    mime_type: str
    sha256: str
    file_size_bytes: int
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None
    page_count: Optional[int] = None
    detected_units: Optional[str] = None
    ingestion_timestamp: str
    source_path: str  # absolute path to the immutable copy


# ---------------------------------------------------------------------------
# Multimodal request manifest
# ---------------------------------------------------------------------------

class MultimodalRequestManifest(BaseModel):
    """Records exactly what was sent to a multimodal model."""
    provider: str
    model: str
    image_path: str
    mime_type: str
    image_width_px: int
    image_height_px: int
    image_byte_size: int
    image_sha256: str
    image_attached: bool  # MUST be True; system fails if False
    prompt_length_chars: int
    request_timestamp: str

    @field_validator("image_attached")
    @classmethod
    def must_have_image(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "image_attached must be True. Sending only structured metadata "
                "to a multimodal model without the actual drawing image is forbidden."
            )
        return v


# ---------------------------------------------------------------------------
# Detected views
# ---------------------------------------------------------------------------

class DetectedView(BaseModel):
    """A drawing view detected in the rendered image."""
    view_id: str
    view_type: ViewType
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""


# ---------------------------------------------------------------------------
# Extracted dimensions
# ---------------------------------------------------------------------------

class DimensionConsensus(BaseModel):
    """Per-dimension agreement record between Claude and Gemini."""
    claude_raw_text: Optional[str] = None
    gemini_raw_text: Optional[str] = None
    claude_value: Optional[float] = None
    gemini_value: Optional[float] = None
    state: ConsensusState = ConsensusState.UNRESOLVED


class ExtractedDimension(BaseModel):
    """A dimension extracted from the 2D drawing image."""
    dimension_id: str
    raw_text: str                  # preserved exactly as seen
    normalized_value: Optional[float] = None
    unit: Optional[str] = None     # mm / inch / degree / etc.
    dimension_type: DimensionType = DimensionType.UNKNOWN
    tolerance_text: Optional[str] = None
    view_id: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    source_provider: str = ""      # "claude" | "gemini"
    consensus: Optional[DimensionConsensus] = None

    @field_validator("normalized_value")
    @classmethod
    def value_must_be_finite(cls, v: Optional[float]) -> Optional[float]:
        import math
        if v is not None and (math.isnan(v) or math.isinf(v)):
            raise ValueError("normalized_value must be finite")
        return v


# ---------------------------------------------------------------------------
# Geometric entities
# ---------------------------------------------------------------------------

class GeometricEntity(BaseModel):
    """A detected graphical entity in the 2D drawing."""
    entity_id: str
    entity_type: EntityType
    view_id: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    source_provider: str = ""


# ---------------------------------------------------------------------------
# Title block metadata
# ---------------------------------------------------------------------------

class TitleBlockField(BaseModel):
    """A single extracted title block metadata field."""
    raw_text: Optional[str] = None
    normalized_value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class TitleBlock(BaseModel):
    """Extracted drawing title block metadata."""
    drawing_title: Optional[TitleBlockField] = None
    drawing_number: Optional[TitleBlockField] = None
    revision: Optional[TitleBlockField] = None
    material: Optional[TitleBlockField] = None
    scale: Optional[TitleBlockField] = None
    units: Optional[TitleBlockField] = None
    projection_method: Optional[TitleBlockField] = None
    general_tolerances: Optional[TitleBlockField] = None
    sheet_size: Optional[TitleBlockField] = None
    author: Optional[TitleBlockField] = None
    company: Optional[TitleBlockField] = None
    notes: List[TitleBlockField] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-provider model result
# ---------------------------------------------------------------------------

class ModelResult(BaseModel):
    """Result from one multimodal AI provider for a drawing analysis."""
    provider: str
    model: str
    views: List[DetectedView] = Field(default_factory=list)
    dimensions: List[ExtractedDimension] = Field(default_factory=list)
    entities: List[GeometricEntity] = Field(default_factory=list)
    title_block: Optional[TitleBlock] = None
    annotations: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    raw_response_sha256: Optional[str] = None
    analysis_timestamp: str = ""
    error: Optional[str] = None          # set if analysis failed


# ---------------------------------------------------------------------------
# Consensus result
# ---------------------------------------------------------------------------

class ViewConsensus(BaseModel):
    view_type: ViewType
    claude_view_id: Optional[str] = None
    gemini_view_id: Optional[str] = None
    state: ConsensusState


class ConsensusResult(BaseModel):
    """Deterministic comparison between Claude and Gemini drawing results."""
    agreed_views: List[ViewConsensus] = Field(default_factory=list)
    disagreed_views: List[ViewConsensus] = Field(default_factory=list)
    agreed_dimensions: List[DimensionConsensus] = Field(default_factory=list)
    disagreed_dimensions: List[DimensionConsensus] = Field(default_factory=list)
    unresolved_dimensions: List[DimensionConsensus] = Field(default_factory=list)
    claude_only_dimensions: List[str] = Field(default_factory=list)   # raw_text values
    gemini_only_dimensions: List[str] = Field(default_factory=list)
    total_claude_dimensions: int = 0
    total_gemini_dimensions: int = 0
    total_agreed: int = 0
    total_disagreed: int = 0
    total_unresolved: int = 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(BaseModel):
    """A single structural validation error in the drawing understanding."""
    field_path: str
    item_id: Optional[str] = None
    message: str
    severity: str = "error"   # "error" | "warning"


# ---------------------------------------------------------------------------
# Phase 18 / 18.1: Engineering Feature Topology & 3D Reconstruction Blueprint
# ---------------------------------------------------------------------------

class FeatureType(str, enum.Enum):
    BASE_BODY = "base_body"
    HOLE = "hole"
    COUNTERBORE = "counterbore"
    SLOT = "slot"
    RIB_LEG = "rib_leg"
    FILLET = "fillet"
    CHAMFER = "chamfer"
    WALL = "wall"
    BOSS = "boss"
    POCKET = "pocket"
    CYLINDRICAL = "cylindrical"
    LINEAR_STEP = "linear_step"
    ARBITRARY_PROFILE = "arbitrary_profile"
    COMPOSITE_PROFILE = "composite_profile"
    EXTRUDED_PROFILE = "extruded_profile"
    BLADE = "blade"
    HUB = "hub"
    LOFT = "loft"
    SWEEP = "sweep"
    REVOLVED_FEATURE = "revolved_feature"
    ROTATIONAL_PATTERN = "rotational_pattern"
    LINEAR_PATTERN = "linear_pattern"
    PATTERNED_FEATURE = "patterned_feature"
    TAPERED_EXTRUSION = "tapered_extrusion"
    FREEFORM_PROFILE = "freeform_profile"
    UNKNOWN = "unknown"


class RotationalPatternData(BaseModel):
    """Specification of a rotational feature pattern array around a 3D axis."""
    source_feature_id: str
    rotation_axis: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])  # e.g. [0, 0, 1] for Z
    count: int = 3                                                                # e.g. 3 blades
    angle_step_deg: float = 120.0                                                 # e.g. 120 deg
    total_angle_deg: float = 360.0                                                # e.g. 360 deg
    center_point: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])   # origin of rotation
    evidence: str = ""


class LinearPatternData(BaseModel):
    """Specification of a linear feature pattern array along a 3D vector."""
    source_feature_id: str
    direction_vector: List[float] = Field(default_factory=lambda: [1.0, 0.0, 0.0])
    count: int = 2
    spacing_mm: float = 10.0
    evidence: str = ""


class KnowledgeState(str, enum.Enum):
    KNOWN = "known"                      # All parameters confirmed by multi-source evidence
    PARTIALLY_KNOWN = "partially_known"  # Core parameters present, minor parameters unconstrained
    AMBIGUOUS = "ambiguous"              # Conflicting model evidence (type or view)
    UNRESOLVED = "unresolved"            # Insufficient geometric context


class AxisAssignment(str, enum.Enum):
    X_WIDTH = "X_WIDTH"
    Y_DEPTH = "Y_DEPTH"
    Z_HEIGHT = "Z_HEIGHT"
    XZ_FRONT = "XZ_FRONT"    # Front view linear, orientation unconfirmed
    XY_TOP = "XY_TOP"        # Top view linear, orientation unconfirmed
    YZ_SIDE = "YZ_SIDE"      # Left/Right view linear, orientation unconfirmed
    XY_BOTTOM = "XY_BOTTOM"  # Bottom view linear, orientation unconfirmed
    UNKNOWN = "UNKNOWN"


class FeatureEvidenceRecord(BaseModel):
    """Traceable evidence bundle linking a feature to raw drawing callouts & entities."""
    source_dimension_ids: List[str] = Field(default_factory=list)
    source_dimension_texts: List[str] = Field(default_factory=list)
    source_entity_ids: List[str] = Field(default_factory=list)
    source_view_ids: List[str] = Field(default_factory=list)
    claude_types: List[str] = Field(default_factory=list)
    gemini_types: List[str] = Field(default_factory=list)
    consensus_states: List[str] = Field(default_factory=list)
    inference_rules: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)


class FeatureParameter(BaseModel):
    """A semantic engineering parameter of a physical feature."""
    param_name: str                        # "width", "height", "depth", "diameter", "radius", "thickness"
    value: float
    unit: str = "mm"
    source_dimension_id: Optional[str] = None
    source_dimension_text: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class DrawingFeature(BaseModel):
    """A synthesized engineering feature recognized from multi-view callouts."""
    feature_id: str                        # "FEAT_001"
    feature_type: FeatureType
    name: str                              # Neutral or evidence-backed engineering description
    knowledge_state: KnowledgeState = KnowledgeState.KNOWN
    controlling_view_types: List[ViewType] = Field(default_factory=list)
    parameters: List[FeatureParameter] = Field(default_factory=list)
    profile_curves: List[ProfileCurve] = Field(default_factory=list)
    rotational_pattern: Optional[RotationalPatternData] = None
    linear_pattern: Optional[LinearPatternData] = None
    bbox_union: Optional[BoundingBox] = None
    evidence: str = ""
    evidence_record: Optional[FeatureEvidenceRecord] = None
    ambiguity_reasons: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class CrossViewAlignment(BaseModel):
    """Orthographic projection alignment linking dimensions to principal 3D axes."""
    width_x_dimensions: List[str] = Field(default_factory=list)   # X-axis callouts
    depth_y_dimensions: List[str] = Field(default_factory=list)   # Y-axis callouts
    height_z_dimensions: List[str] = Field(default_factory=list)  # Z-axis callouts
    axis_uncertainty: Dict[str, str] = Field(default_factory=dict)
    unassigned_dimensions: List[str] = Field(default_factory=list)
    estimated_envelope_3d: Dict[str, Optional[float]] = Field(default_factory=dict)


class CSGOperation(BaseModel):
    """A single sequential solid modeling step in the reconstruction recipe."""
    step: int
    operation_type: str                    # "base_extrusion", "pocket_cutout", "through_hole", "fillet"
    target_feature_id: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ReconstructionBlueprint(BaseModel):
    """Deterministic CSG reconstruction blueprint ready for 3D modeling."""
    envelope_3d: Dict[str, Optional[float]] = Field(default_factory=dict)
    ordered_operations: List[CSGOperation] = Field(default_factory=list)
    constraint_status: str = "fully_constrained"   # "fully_constrained" | "partially_constrained" | "under_constrained"
    completeness_score: float = Field(ge=0.0, le=1.0, default=1.0)
    ambiguous_features: List[str] = Field(default_factory=list)
    missing_parameters: List[str] = Field(default_factory=list)


class FeatureGraph(BaseModel):
    """Topological graph of mechanical features and their cross-view constraints."""
    features: List[DrawingFeature] = Field(default_factory=list)
    cross_view_alignment: Optional[CrossViewAlignment] = None
    blueprint: Optional[ReconstructionBlueprint] = None
    primary_strategy: Optional[str] = None
    synthesis_timestamp: str = ""


# ---------------------------------------------------------------------------
# Top-level drawing understanding
# ---------------------------------------------------------------------------

class DrawingUnderstanding(BaseModel):
    """Complete structured understanding of a 2D engineering drawing. UC2 root object."""
    project_id: str
    source: DrawingSource
    normalized_png_path: Optional[str] = None
    normalized_png_sha256: Optional[str] = None
    claude_manifest: Optional[MultimodalRequestManifest] = None
    gemini_manifest: Optional[MultimodalRequestManifest] = None
    claude_result: Optional[ModelResult] = None
    gemini_result: Optional[ModelResult] = None
    consensus: Optional[ConsensusResult] = None
    validation_errors: List[ValidationError] = Field(default_factory=list)
    validation_passed: bool = False
    render_quality: Optional[str] = None
    render_notes: Optional[str] = None
    render_error: Optional[str] = None
    feature_graph: Optional[FeatureGraph] = None
    understanding_timestamp: str = ""

    # Convenience accessors
    @property
    def all_agreed_dimensions(self) -> List[DimensionConsensus]:
        if self.consensus:
            return self.consensus.agreed_dimensions
        return []

    @property
    def all_dimensions_combined(self) -> List[ExtractedDimension]:
        """Union of Claude and Gemini dimensions (deduplicated by raw_text where agreed)."""
        seen: Dict[str, bool] = {}
        result = []
        for d in (self.claude_result.dimensions if self.claude_result else []):
            if d.raw_text not in seen:
                seen[d.raw_text] = True
                result.append(d)
        for d in (self.gemini_result.dimensions if self.gemini_result else []):
            if d.raw_text not in seen:
                seen[d.raw_text] = True
                result.append(d)
        return result


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------

class DrawingProjectCreateResponse(BaseModel):
    project_id: str
    filename: str
    status: str
    created_at: str
    sha256: str
    file_size_bytes: int


class DrawingProjectStatusResponse(BaseModel):
    project_id: str
    filename: str
    status: str
    created_at: str
    updated_at: str
    sha256: str
    file_size_bytes: int
    analysis_complete: bool = False
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
