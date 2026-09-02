"""Phase 21 — Moldability Analysis Data Models and Schemas.

Dedicated schema for geometry-driven, evidence-based injection moldability analysis
operating downstream of validated FreeCAD / OpenCASCADE B-Rep models.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class MoldAnalysisStatus(str, Enum):
    """Overall status of moldability analysis."""
    NOT_STARTED = "NOT_STARTED"
    PROCESSING = "PROCESSING"
    REQUIRES_USER_INPUT = "REQUIRES_USER_INPUT"
    ANALYZED = "ANALYZED"
    MOLDABLE = "MOLDABLE"
    MOLDABLE_WITH_SIDE_ACTIONS = "MOLDABLE_WITH_SIDE_ACTIONS"
    MOLDABILITY_WARNING = "MOLDABILITY_WARNING"
    MOLDABILITY_BLOCKED = "MOLDABILITY_BLOCKED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class DraftClassification(str, Enum):
    """Classification of a B-Rep face relative to pull direction."""
    POSITIVE_DRAFT = "POSITIVE_DRAFT"
    NEGATIVE_DRAFT = "NEGATIVE_DRAFT"
    ZERO_DRAFT = "ZERO_DRAFT"
    INSUFFICIENT_DRAFT = "INSUFFICIENT_DRAFT"
    NOT_RELEVANT = "NOT_RELEVANT"


class UndercutClassification(str, Enum):
    """Classification of a geometric region for mold withdrawal."""
    DIRECTLY_EJECTABLE = "DIRECTLY_EJECTABLE"
    UNDERCUT = "UNDERCUT"
    AMBIGUOUS = "AMBIGUOUS"
    NON_MOLD_RELEVANT = "NON_MOLD_RELEVANT"


class SliderClassification(str, Enum):
    """Classification of slider / side-action feasibility."""
    SLIDER_REQUIRED = "SLIDER_REQUIRED"
    SLIDER_POSSIBLE = "SLIDER_POSSIBLE"
    SLIDER_NOT_REQUIRED = "SLIDER_NOT_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"


class LifterClassification(str, Enum):
    """Classification of lifter mechanism feasibility."""
    LIFTER_REQUIRED = "LIFTER_REQUIRED"
    LIFTER_POSSIBLE = "LIFTER_POSSIBLE"
    LIFTER_NOT_REQUIRED = "LIFTER_NOT_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"


class SurfaceSideClassification(str, Enum):
    """Classification of surface into mold halves / mechanisms."""
    CAVITY_SIDE = "CAVITY_SIDE"
    CORE_SIDE = "CORE_SIDE"
    PARTING_REGION = "PARTING_REGION"
    SIDE_ACTION_REGION = "SIDE_ACTION_REGION"
    UNRESOLVED = "UNRESOLVED"


class EjectionClassification(str, Enum):
    """Classification of part demolding and ejection feasibility."""
    EJECTION_FEASIBLE = "EJECTION_FEASIBLE"
    EJECTION_WITH_SIDE_ACTIONS = "EJECTION_WITH_SIDE_ACTIONS"
    EJECTION_BLOCKED = "EJECTION_BLOCKED"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"


class CandidateDirection(BaseModel):
    """Candidate mold opening direction evaluated on geometry."""
    direction_id: str
    vector: List[float] = Field(description="Unit vector [dx, dy, dz]")
    label: str = Field(description="Display label, e.g. +Z, -Z, +Y, Custom")
    undercut_area: float = Field(default=0.0, description="Estimated undercut surface area (mm²)")
    undercut_face_count: int = Field(default=0, description="Count of undercut faces")
    obstructed_faces: List[str] = Field(default_factory=list, description="IDs of obstructed faces")
    draft_violations: int = Field(default=0, description="Count of faces with negative or insufficient draft")
    score: float = Field(default=0.0, description="Composite optimality score (0.0 to 1.0, higher is better)")
    notes: Optional[str] = None


class FaceDraftInfo(BaseModel):
    """Draft analysis for a single B-Rep face."""
    face_id: str
    face_index: int
    surface_type: str
    area: float
    face_normal: Optional[List[float]] = None
    center: Optional[List[float]] = None
    angle_to_pull_deg: float = Field(description="Angle between face normal and pull vector in degrees")
    draft_angle_deg: float = Field(description="Effective draft angle from parting plane in degrees")
    classification: DraftClassification
    status: str = Field(description="PASS, WARNING, or FAIL")
    confidence: float = 1.0
    evidence: Optional[str] = None


class DraftAnalysisResult(BaseModel):
    """Comprehensive draft angle analysis across all faces."""
    status: str = "ANALYZED"
    mold_opening_direction: List[float]
    minimum_draft_angle_deg: Optional[float] = Field(
        default=None,
        description="Minimum acceptable draft angle from user or evidence; None if unspecified",
    )
    is_minimum_draft_user_configured: bool = False
    total_faces_evaluated: int = 0
    positive_draft_count: int = 0
    negative_draft_count: int = 0
    zero_draft_count: int = 0
    insufficient_draft_count: int = 0
    not_relevant_count: int = 0
    pass_percentage: float = 0.0
    warning_percentage: float = 0.0
    fail_percentage: float = 0.0
    faces: List[FaceDraftInfo] = Field(default_factory=list)


class UndercutFeature(BaseModel):
    """Geometrically identified undercut region."""
    undercut_id: str
    face_ids: List[str]
    surface_area: float
    location: List[float] = Field(description="Centroid [x, y, z] of undercut region")
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    blocking_direction: List[float] = Field(description="Vector along which mold movement is blocked")
    required_withdrawal_direction: List[float] = Field(description="Vector required to free the undercut")
    classification: UndercutClassification = UndercutClassification.UNDERCUT
    confidence: float = 1.0
    evidence: str = Field(description="Provenance trace back to B-Rep face geometry")
    possible_resolution: str = Field(description="e.g. SLIDER, LIFTER, REDESIGN")


class UndercutAnalysisResult(BaseModel):
    """Result of geometric undercut detection."""
    status: str = "NO_UNDERCUTS_DETECTED"
    total_undercuts: int = 0
    total_undercut_area: float = 0.0
    undercuts: List[UndercutFeature] = Field(default_factory=list)
    directly_ejectable_face_count: int = 0
    undercut_face_count: int = 0
    ambiguous_face_count: int = 0
    face_classifications: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of face_id -> DIRECTLY_EJECTABLE | UNDERCUT | AMBIGUOUS",
    )


class SliderCandidate(BaseModel):
    """Potential side-action slider mechanism derived from undercut geometry."""
    slider_id: str
    undercut_id: str
    withdrawal_direction: List[float] = Field(description="Unit vector for side-action pull")
    required_travel: float = Field(description="Minimum geometric stroke/travel required (mm) derived from geometry")
    affected_faces: List[str] = Field(default_factory=list)
    interference_faces: List[str] = Field(default_factory=list)
    feasibility: SliderClassification = SliderClassification.SLIDER_REQUIRED
    confidence: float = 1.0
    provenance: str = Field(description="Geometry source trace")


class SliderAnalysisResult(BaseModel):
    """Analysis of side-action slider candidates."""
    status: SliderClassification = SliderClassification.SLIDER_NOT_REQUIRED
    candidates: List[SliderCandidate] = Field(default_factory=list)
    slider_count: int = 0
    summary: str = ""


class LifterCandidate(BaseModel):
    """Potential internal lifter mechanism derived from internal undercut geometry."""
    lifter_id: str
    undercut_id: str
    undercut_geometry_center: List[float]
    withdrawal_direction: List[float]
    ejection_direction: List[float]
    lifter_axis: List[float] = Field(description="Unit vector defining the lifter angle of motion")
    lifter_angle_deg: float = Field(description="Angle of lifter travel relative to ejection axis in degrees")
    required_travel: float = Field(description="Travel distance along lifter axis derived from undercut depth")
    affected_faces: List[str] = Field(default_factory=list)
    interference_faces: List[str] = Field(default_factory=list)
    feasibility: LifterClassification = LifterClassification.LIFTER_REQUIRED
    confidence: float = 1.0
    provenance: str = Field(description="Geometry source trace")


class LifterAnalysisResult(BaseModel):
    """Analysis of internal lifter candidates."""
    status: LifterClassification = LifterClassification.LIFTER_NOT_REQUIRED
    candidates: List[LifterCandidate] = Field(default_factory=list)
    lifter_count: int = 0
    summary: str = ""


class PartingCandidate(BaseModel):
    """Candidate parting line / boundary region solution."""
    candidate_id: str
    label: str
    parting_edges: List[str] = Field(default_factory=list, description="IDs of boundary edges lying on parting line")
    parting_segments: List[List[float]] = Field(default_factory=list, description="3D line segments for visualization")
    plane_z_approx: Optional[float] = None
    is_planar: bool = False
    feasibility_score: float = 1.0
    cavity_face_count: int = 0
    core_face_count: int = 0
    is_recommended: bool = False
    notes: Optional[str] = None


class PartingLineAnalysisResult(BaseModel):
    """Analysis of candidate parting lines and boundary transition regions."""
    status: str = "ANALYZED"
    recommended_candidate_id: Optional[str] = None
    candidates: List[PartingCandidate] = Field(default_factory=list)
    transition_edges_count: int = 0


class CoreCavityAnalysisResult(BaseModel):
    """Surface classification into core, cavity, parting, and side actions."""
    status: str = "ANALYZED"
    cavity_faces: List[str] = Field(default_factory=list)
    core_faces: List[str] = Field(default_factory=list)
    parting_faces: List[str] = Field(default_factory=list)
    side_action_faces: List[str] = Field(default_factory=list)
    unresolved_faces: List[str] = Field(default_factory=list)
    cavity_area: float = 0.0
    core_area: float = 0.0
    parting_area: float = 0.0
    side_action_area: float = 0.0
    face_side_map: Dict[str, SurfaceSideClassification] = Field(default_factory=dict)


class EjectionAnalysisResult(BaseModel):
    """Demolding and ejection feasibility analysis."""
    status: EjectionClassification = EjectionClassification.EJECTION_FEASIBLE
    ejection_direction: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    blocking_regions: List[Dict[str, Any]] = Field(default_factory=list)
    trapped_volumes_count: int = 0
    side_actions_required_count: int = 0
    confidence: float = 1.0
    summary: str = ""


class MoldParameters(BaseModel):
    """User-configured or evidence-extracted manufacturing parameters."""
    mold_opening_direction: Optional[List[float]] = Field(
        default=None,
        description="User-selected mold pull unit vector [dx, dy, dz]",
    )
    direction_label: Optional[str] = Field(default=None, description="e.g. +Z, -Z, +Y, etc.")
    material: Optional[str] = Field(default=None, description="e.g. ABS, PP, POM, PC")
    shrinkage: Optional[float] = Field(default=None, description="Material volumetric shrinkage rate %")
    minimum_draft_angle: Optional[float] = Field(
        default=None,
        description="Minimum acceptable draft angle in degrees",
    )
    mold_configuration: Optional[str] = Field(
        default="TWO_PLATE",
        description="TWO_PLATE, THREE_PLATE, SIDE_ACTION, etc.",
    )
    user_configured_fields: List[str] = Field(
        default_factory=list,
        description="Explicit list of parameters configured as USER_INPUT",
    )


class ProvenanceInfo(BaseModel):
    """Provenance tracking connecting analysis back to source geometry."""
    reconstruction_id: Optional[str] = None
    artifact_hash: Optional[str] = None
    source_type: str = "BREP_SOLID"  # "2D_RECONSTRUCTED_BREP" | "STEP_IMPORTED_BREP"
    source_filename: Optional[str] = None
    solid_count: int = 1
    total_face_count: int = 0
    total_edge_count: int = 0
    volume_mm3: float = 0.0
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    units: str = "mm"
    model_coordinate_system: str = "XYZ"


class MoldAnalysisResult(BaseModel):
    """Complete, integrated result schema for downstream moldability analysis."""
    analysis_id: str
    reconstruction_id: Optional[str] = None
    artifact_hash: Optional[str] = None
    status: MoldAnalysisStatus = MoldAnalysisStatus.NOT_STARTED
    is_valid_brep: bool = True
    active_mold_opening_direction: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    candidate_directions: List[CandidateDirection] = Field(default_factory=list)
    
    mold_parameters: MoldParameters = Field(default_factory=MoldParameters)
    draft_analysis: DraftAnalysisResult = Field(
        default_factory=lambda: DraftAnalysisResult(mold_opening_direction=[0.0, 0.0, 1.0])
    )
    undercut_analysis: UndercutAnalysisResult = Field(default_factory=UndercutAnalysisResult)
    slider_analysis: SliderAnalysisResult = Field(default_factory=SliderAnalysisResult)
    lifter_analysis: LifterAnalysisResult = Field(default_factory=LifterAnalysisResult)
    parting_line_analysis: PartingLineAnalysisResult = Field(default_factory=PartingLineAnalysisResult)
    core_cavity_analysis: CoreCavityAnalysisResult = Field(default_factory=CoreCavityAnalysisResult)
    ejection_analysis: EjectionAnalysisResult = Field(default_factory=EjectionAnalysisResult)

    overall_moldability: str = "MOLDABLE"
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    provenance: ProvenanceInfo = Field(default_factory=ProvenanceInfo)
    analysis_timestamp: str = ""
