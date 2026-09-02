"""Phase 19A — Remediated Schemas for Deterministic 2D -> 3D Reconstruction Blueprint.

Includes explicit feature placement (2D/3D centers & normals), hole termination modes,
boss extrusion depths, fillet edge selection constraints, and truthful execution statuses
(READY, PARTIALLY_CONSTRAINED, BLOCKED_MISSING_PARAMETER, SKIPPED_AMBIGUOUS).
"""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.drawing.schemas import (
    BoundingBox,
    FeatureType,
    KnowledgeState,
    ViewType,
)


class ReconstructionStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"                             # 100% confirmed envelope and all feature parameters
    PARTIAL_ASSUMED = "PARTIAL_ASSUMED"               # Contains unconstrained or partially constrained parameters
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"   # Missing critical base envelope dimensions


class StepExecutionStatus(str, enum.Enum):
    READY = "READY"                                   # Every required geometric parameter is known from evidence
    PARTIALLY_CONSTRAINED = "PARTIALLY_CONSTRAINED"   # Profile known, but position or depth/extent is unconstrained
    BLOCKED_MISSING_PARAMETER = "BLOCKED_MISSING_PARAMETER" # Critical prerequisite parameter missing (e.g. base height)
    SKIPPED_AMBIGUOUS = "SKIPPED_AMBIGUOUS"           # Conflicting multi-model evidence prevents deterministic solid creation


class HoleTermination(str, enum.Enum):
    THROUGH_ALL = "THROUGH_ALL"                       # Explicit through-hole evidence ("THRU" note, through-line)
    BLIND = "BLIND"                                   # Blind hole with explicit depth parameter
    DEPTH_UNKNOWN = "DEPTH_UNKNOWN"                   # Hole callout present, but termination depth is unconstrained


class EdgeSelectionStatus(str, enum.Enum):
    UNIQUE = "UNIQUE"                                 # Candidate edges uniquely identified by drawing geometry
    UNCONSTRAINED = "UNCONSTRAINED"                   # Radius callout present, but target edge identity is unconstrained


class SketchPlane(str, enum.Enum):
    XY_TOP = "XY_TOP"              # Normal along +Z (Top/Bottom view reference)
    XZ_FRONT = "XZ_FRONT"          # Normal along +Y (Front/Rear view reference)
    YZ_SIDE = "YZ_SIDE"            # Normal along +X (Left/Right view reference)
    OFFSET_PLANE = "OFFSET_PLANE"


class CADProfileType(str, enum.Enum):
    RECTANGLE = "rectangle"
    CIRCULAR = "circular"
    SLOT = "slot"
    POLYGON = "polygon"
    ARCS_AND_LINES = "arcs_and_lines"
    UNCONSTRAINED = "unconstrained"


class CADOperationType(str, enum.Enum):
    BASE_EXTRUDE = "base_extrude"
    CUT_EXTRUDE = "cut_extrude"
    HOLE_DRILL = "hole_drill"
    BOSS_EXTRUDE = "boss_extrude"
    CYLINDRICAL_FEATURE = "cylindrical_feature"
    EDGE_FILLET = "edge_fillet"
    EDGE_CHAMFER = "edge_chamfer"


class FeaturePlacement(BaseModel):
    """Explicit geometric placement of a feature on its reference plane."""
    center_2d_u: Optional[float] = None        # U coordinate in reference sketch plane (mm)
    center_2d_v: Optional[float] = None        # V coordinate in reference sketch plane (mm)
    position_status: str = "UNCONSTRAINED"     # "CONSTRAINED" | "UNCONSTRAINED"
    position_evidence: Optional[str] = None    # e.g. "Center mark ENT_001 at (u, v)" or "Unconstrained position"
    normal_vector: Optional[List[float]] = None # e.g. [0.0, 0.0, 1.0] for XY_TOP


class OperationValidity(str, enum.Enum):
    """Phase 19A.2 Operation Validity classification for deterministic CAD execution."""
    EXECUTABLE = "EXECUTABLE"                         # Complete location + direction + magnitude + termination + target topology
    PARTIALLY_EXECUTABLE = "PARTIALLY_EXECUTABLE"     # Base profile known, but height/depth unconstrained
    UNCONSTRAINED = "UNCONSTRAINED"                   # Location, termination, or edge identity missing from 2D drawing
    AMBIGUOUS = "AMBIGUOUS"                           # Conflicting multi-model semantic evidence
    BLOCKED = "BLOCKED"                               # Missing prerequisite parameters or blocked by unconstrained parent


class EvidenceAuditRecord(BaseModel):
    """Phase 19A.2 per-operation evidence audit record across 7 dimensions."""
    step_id: str
    operation_type: CADOperationType
    target_feature_id: str
    target_feature_type: FeatureType

    # 1. Location
    location_status: str                              # "CONSTRAINED" | "UNCONSTRAINED"
    location_derivation: Optional[str] = None
    location_xyz: Optional[List[float]] = None
    reference_plane_or_face: Optional[str] = None
    source_tier_a_location_evidence: List[str] = Field(default_factory=list)
    source_tier_b_location_evidence: Optional[str] = None

    # 2. Direction
    direction_status: str                             # "CONSTRAINED" | "UNCONSTRAINED"
    direction_vector: Optional[List[float]] = None
    direction_reference_view: Optional[str] = None

    # 3. Termination
    termination_type: str                             # "THROUGH_ALL" | "BLIND" | "DEPTH_UNKNOWN" | "NOT_APPLICABLE"
    termination_depth_mm: Optional[float] = None
    termination_evidence: Optional[str] = None

    # 4. Magnitude
    magnitude_name: str                               # "width_x/depth_y/height_z", "diameter", "radius"
    magnitude_value_mm: Optional[float] = None
    tier_a_dim_id: Optional[str] = None
    tier_a_raw_text: Optional[str] = None

    # 5. Target Topology
    target_topology_entity: Optional[str] = None      # e.g. "Global Origin (0,0,0)", "UNCONSTRAINED_EDGE"
    target_topology_status: str = "UNCONSTRAINED"     # "DERIVED" | "UNCONSTRAINED"

    # 6. Operation Validity
    validity: OperationValidity
    blocking_reasons: List[str] = Field(default_factory=list)

    # 7. Provenance Chain
    provenance_chain: Dict[str, Any] = Field(default_factory=dict)


class ReconstructionEvidenceAudit(BaseModel):
    """Phase 19A.2 aggregate evidence audit summary and Hard 19B Gate declaration."""
    project_id: str
    total_operations: int
    executable_count: int
    partially_executable_count: int
    unconstrained_count: int
    ambiguous_count: int
    blocked_count: int
    gate_19b_passed: bool = False
    gate_19b_status: str = "HARD_GATE_LOCKED_MISSING_EVIDENCE" # "GATE_OPEN_READY_FOR_CAD" | "HARD_GATE_LOCKED_MISSING_EVIDENCE"
    gate_19b_rationale: str = ""
    records: List[EvidenceAuditRecord] = Field(default_factory=list)
    audit_timestamp: str = ""


class ParametricParameter(BaseModel):
    """A parameter in the CAD reconstruction DAG with strict Tier A/B/C provenance."""
    name: str                                  # "width_x", "depth_y", "height_z", "diameter", "radius", "depth"
    value: Optional[float]                     # None if unconstrained
    unit: str = "mm"
    source_tier_a_dim_id: Optional[str] = None # e.g. "DIMG_014"
    source_tier_a_text: Optional[str] = None   # e.g. "70.04"
    tier_b_feature_id: str                     # e.g. "FEAT_001"
    is_assumed: bool = False                   # True if parameter is an assumed fallback
    assumption_rationale: Optional[str] = None # e.g. "Requires human confirmation"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class ParametricCADStep(BaseModel):
    """An ordered deterministic step in the CAD reconstruction recipe."""
    step_index: int                            # 1, 2, 3...
    step_id: str                               # "CAD_STEP_001"
    operation_type: CADOperationType
    target_feature_id: str                     # "FEAT_001"
    target_feature_type: FeatureType
    description: str
    sketch_plane: SketchPlane
    profile_type: CADProfileType
    placement: FeaturePlacement = Field(default_factory=FeaturePlacement)
    hole_termination: Optional[HoleTermination] = None
    extrusion_depth: Optional[ParametricParameter] = None
    edge_selection_status: Optional[EdgeSelectionStatus] = None
    candidate_edge_evidence: List[str] = Field(default_factory=list)
    parameters: Dict[str, ParametricParameter] = Field(default_factory=dict)
    controlling_views: List[ViewType] = Field(default_factory=list)
    tier_a_entity_ids: List[str] = Field(default_factory=list)
    knowledge_state: KnowledgeState = KnowledgeState.KNOWN
    execution_status: StepExecutionStatus
    operation_validity: OperationValidity = OperationValidity.UNCONSTRAINED
    evidence_audit: Optional[EvidenceAuditRecord] = None
    required_parameters: List[str] = Field(default_factory=list)
    known_parameters: List[str] = Field(default_factory=list)
    unknown_parameters: List[str] = Field(default_factory=list)
    unresolved_notes: List[str] = Field(default_factory=list)


class ParametricReconstructionPlan(BaseModel):
    """Complete 19A Reconstruction Blueprint ready for CAD kernel execution."""
    project_id: str
    reconstruction_status: ReconstructionStatus
    envelope_3d: Dict[str, Optional[float]] = Field(default_factory=dict)
    steps: List[ParametricCADStep] = Field(default_factory=list)
    evidence_audit: Optional[ReconstructionEvidenceAudit] = None
    unconstrained_parameters: List[str] = Field(default_factory=list)
    ambiguous_features_skipped: List[str] = Field(default_factory=list)
    is_fully_reconstructible: bool = False
    plan_notes: List[str] = Field(default_factory=list)
    plan_timestamp: str = ""
