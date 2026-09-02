"""Pydantic schemas for CAD Intelligence FastAPI service."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Project Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ProjectCreateResponse(BaseModel):
    project_id: str = Field(..., description="Unique UUID identifier for the CAD project")
    filename: str = Field(..., description="Original name of the uploaded STEP file")
    status: str = Field(..., description="Current processing status")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    sha256_hash: Optional[str] = Field(None, description="Cryptographic SHA-256 hash of original STEP file")
    file_size_bytes: Optional[int] = Field(None, description="Size of uploaded STEP file in bytes")


class DrawingArtifactSchema(BaseModel):
    artifact_id: str = Field(..., description="Identifier for downloading the artifact")
    artifact_type: str = Field(..., description="File format/type (fcstd, svg, dxf, json, txt)")
    filename: str = Field(..., description="File name on disk")
    size_bytes: int = Field(..., description="File size in bytes")
    download_url: str = Field(..., description="API endpoint to download this artifact")


class ProjectStatusResponse(BaseModel):
    project_id: str
    filename: str
    status: str
    created_at: str
    updated_at: str
    sha256_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    artifacts: List[DrawingArtifactSchema] = Field(default_factory=list)
    error_message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Schemas
# ─────────────────────────────────────────────────────────────────────────────

class BoundingBoxSchema(BaseModel):
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    x_length: float
    y_length: float
    z_length: float


class TopologyCountsSchema(BaseModel):
    solids: int
    shells: int
    faces: int
    edges: int
    vertices: int


class AnalysisSummarySchema(BaseModel):
    project_id: str
    filename: str
    units: str
    topology: TopologyCountsSchema
    bounding_box: BoundingBoxSchema
    surface_types: Dict[str, int]
    feature_count: int
    volume_mm3: float
    surface_area_mm2: float
    sha256_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    source_file: Optional[str] = None
    analysis_timestamp: Optional[str] = None
    validation_status: str = Field("VALID_GEOMETRY", description="VALID_GEOMETRY or INVALID_GEOMETRY")
    validation_message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Feature Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FeatureItemSchema(BaseModel):
    id: str
    type: str
    status: str
    dimensions: Dict[str, Any]
    source_entities: List[str]
    axis: Optional[List[float]] = None
    position: Optional[List[float]] = None


class FeatureListResponse(BaseModel):
    project_id: str
    total_features: int
    features: List[FeatureItemSchema]


# ─────────────────────────────────────────────────────────────────────────────
# Dimension Schemas
# ─────────────────────────────────────────────────────────────────────────────

class DimensionItemSchema(BaseModel):
    id: str
    type: str
    value: float
    display_value: str
    unit: str
    semantic_role: str
    priority: str
    dependency_type: str
    depends_on: List[str] = Field(default_factory=list)
    source_feature: Optional[str] = None
    source_entities: List[str] = Field(default_factory=list)
    status: str
    selected_view: Optional[str] = None
    projection_status: str = "unsuitable"
    placement_status: str = "excluded"
    x_mm: float = 0.0
    y_mm: float = 0.0
    reason: str = ""
    category: str = "candidate"
    exclusion_reason: Optional[str] = None


class FeatureCoverageSchema(BaseModel):
    feature_id: str
    feature_type: str
    coverage_status: str
    dimension_ids: List[str]
    placed_dimension_ids: List[str]
    missing_aspects: List[str] = Field(default_factory=list)


class DimensionListResponse(BaseModel):
    project_id: str
    raw_measurements_count: int = 0
    engineering_candidates_count: int = 0
    total_candidates: int
    placed_count: int
    excluded_count: int
    dimensions: List[DimensionItemSchema]
    feature_coverages: List[FeatureCoverageSchema] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Drawing Schemas
# ─────────────────────────────────────────────────────────────────────────────

class DrawingGenerateRequest(BaseModel):
    projection: str = Field("third-angle", description="Projection angle: third-angle or first-angle")
    template: str = Field("A3_Landscape_blank.svg", description="Drawing sheet template SVG")
    scale: float = Field(0.0, description="Drawing scale (0.0 for automatic scale)")


class DrawingResponse(BaseModel):
    project_id: str
    status: str
    drawing_type: str
    artifacts: List[DrawingArtifactSchema]


# ─────────────────────────────────────────────────────────────────────────────
# AI Engineering Review Schemas (Phase 11)
# ─────────────────────────────────────────────────────────────────────────────

class AIReviewRequest(BaseModel):
    provider: str = Field("mock", description="AI reasoning provider: mock, claude, gemini")
    model: Optional[str] = Field(None, description="Optional custom model override")


class AIRecommendationSchema(BaseModel):
    recommendation_id: str
    action: str
    dimension_id: Optional[str] = None
    feature_id: Optional[str] = None
    selected_view: Optional[str] = None
    reason: str
    confidence: float
    requires_human_review: bool
    evidence: List[str] = Field(default_factory=list)
    validation_status: str
    validation_notes: List[str] = Field(default_factory=list)
    requires_new_cad_analysis: bool = False


class AIReviewResponse(BaseModel):
    project_id: str
    review_id: str
    provider: str
    model: str
    overall_assessment: str
    good_aspects: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)
    recommendations: List[AIRecommendationSchema] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    requires_human_review: bool
    stats: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[DrawingArtifactSchema] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 19B CAD Reconstruction Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionRequest(BaseModel):
    partial_mode: bool = Field(
        True,
        description="Allow PARTIALLY_EXECUTABLE operations to run with placeholder values",
    )


class ExecutionResponse(BaseModel):
    project_id: str
    success: bool
    gate_passed: bool
    gate_status: str
    executable_count: int
    partial_count: int
    skipped_count: int
    failed_count: int
    error_message: Optional[str] = None
    created_at: str = ""
    summary: str = ""


class ReconstructionPlanRequest(BaseModel):
    force_regenerate: bool = Field(
        False,
        description="Force regeneration of the 19A plan even if cached",
    )


class ReconstructionPlanResponse(BaseModel):
    project_id: str
    reconstruction_status: str
    gate_19b_passed: bool
    gate_19b_status: str
    gate_19b_rationale: str
    is_fully_reconstructible: bool
    total_steps: int
    steps_summary: Dict[str, int]
    plan_timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# Phase 26 Moldability, Undercut & Slider Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FaceDraftResultSchema(BaseModel):
    face_id: str
    surface_type: str
    classification: str
    draft_angle_deg: float
    min_draft_deg: float
    max_draft_deg: float
    area_mm2: float
    center: List[float]
    normal: List[float]
    is_occluded: bool = False
    occlusion_depth_mm: float = 0.0
    side_action_candidate: bool = False


class PartingCurveSegmentSchema(BaseModel):
    segment_id: str
    points: List[List[float]]
    length_mm: float
    connected_faces: List[str] = Field(default_factory=list)


class MoldDirectionEvaluationSchema(BaseModel):
    direction: List[float]
    direction_name: str
    cavity_face_count: int
    core_face_count: int
    undercut_face_count: int
    undercut_area_mm2: float
    insufficient_draft_count: int
    projected_area_mm2: float
    estimated_clamping_tonnage: float
    moldability_score: float


class SliderActionSchema(BaseModel):
    slider_id: str
    mechanism_type: str
    pull_vector: List[float]
    pull_direction_description: str = Field(default="")
    required_stroke_mm: float
    recommended_cam_angle_deg: float
    source_faces: List[str]
    undercut_area_mm2: float
    cluster_center: List[float] = Field(default_factory=list)
    arrow_start: List[float]
    arrow_end: List[float]
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    estimated_tooling_cost_usd: float = Field(default=0.0)
    dfm_elimination_advice: str
    is_eliminatable_by_shutoff: bool = Field(default=False)
    is_eliminatable_via_redesign: bool = Field(default=False)
    vector_verification: Dict[str, Any] = Field(default_factory=dict)



class MoldAnalysisResponse(BaseModel):
    project_id: str
    optimal_pull_direction: List[float]
    optimal_direction_name: str
    min_draft_threshold_deg: float
    total_faces: int
    cavity_faces: List[str]
    core_faces: List[str]
    insufficient_draft_faces: List[str]
    undercut_faces: List[str]
    total_surface_area_mm2: float
    cavity_area_mm2: float
    core_area_mm2: float
    undercut_area_mm2: float
    insufficient_draft_area_mm2: float
    projected_area_mm2: float
    estimated_clamping_tonnage: float
    estimated_cavity_pressure_bar: float
    parting_lines: List[PartingCurveSegmentSchema]
    face_details: Dict[str, FaceDraftResultSchema]
    direction_evaluations: List[MoldDirectionEvaluationSchema]
    sliders: List[SliderActionSchema] = Field(default_factory=list)
    moldability_score: float
    tooling_recommendations: List[str] = Field(default_factory=list)


class EvaluateMoldDirectionRequest(BaseModel):
    direction: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0], description="Custom 3D pull direction vector [dx, dy, dz]")
    min_draft_deg: float = Field(1.5, description="Minimum draft threshold in degrees")
    cavity_pressure_bar: float = Field(400.0, description="Injection molding cavity pressure in bar")
    preset_id: str = Field("GENERAL_PLASTIC_INJECTION", description="Process profile ID")


# ─────────────────────────────────────────────────────────────────────────────
# Phase M1 Manufacturing Intelligence & Epistemic Evidence Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ManufacturingFindingSchema(BaseModel):
    finding_id: str
    category: str
    severity: str
    knowledge_state: str
    title: str
    source_entities: List[str]
    pull_direction: List[float]
    known_geometry: Dict[str, Any]
    engineering_interpretation: str
    geometric_reasoning: str
    unknowns: List[str]
    recommended_engineer_action: str
    confidence: float
    anchor_point: Optional[List[float]] = None
    vector: Optional[List[float]] = None


class PullDirectionCandidateSchema(BaseModel):
    candidate_id: str
    direction_vector: List[float]
    direction_name: str
    derivation_source: str
    draft_violation_count: int
    draft_violation_area_mm2: float
    potential_undercut_count: int
    undercut_area_mm2: float
    side_action_candidate_count: int
    lifter_candidate_count: int
    transverse_hole_count: int
    projected_area_mm2: float
    estimated_clamping_tonnage: float
    moldability_score: float
    is_geometrically_preferred: bool
    trade_off_analysis: str


class WallThicknessRegionSchema(BaseModel):
    region_id: str
    face_ids: List[str]
    sample_point: List[float]
    measured_thickness_mm: float
    nominal_range_mm: List[float]
    condition: str
    thickness_delta_pct: float
    sink_mark_risk_score: float


class RibBossFeatureSchema(BaseModel):
    feature_id: str
    feature_type: str
    face_ids: List[str]
    root_thickness_mm: float
    nominal_wall_thickness_mm: float
    root_to_wall_ratio: float
    max_recommended_ratio: float
    height_mm: float
    draft_angle_deg: float
    is_compliant: bool
    review_note: str


class TransverseHoleSchema(BaseModel):
    hole_id: str
    face_id: str
    diameter_mm: float
    depth_mm: float
    axis_vector: List[float]
    is_through: bool
    angle_to_pull_deg: float
    potential_core_pin_requirement: str
    center_point: List[float]


class ReviewPriorityItemSchema(BaseModel):
    priority_rank: int
    severity: str
    title: str
    finding_id: str
    source_entities: List[str]
    known_geometric_fact: str
    inferred_manufacturing_implication: str
    unknown_factors: List[str]
    alternative_interpretations: List[str]
    recommended_engineer_action: str


class AIManufacturingReviewSchema(BaseModel):
    executive_summary: str
    process_assumption: str
    selected_pull_direction: str
    top_priorities: List[ReviewPriorityItemSchema]
    epistemic_provenance: Dict[str, int]
    general_tooling_guidelines: List[str]


class ManufacturingReviewResponse(BaseModel):
    project_id: str
    preset_used: Dict[str, Any]
    optimal_pull_direction: List[float]
    optimal_direction_name: str
    main_pull_proof: Dict[str, Any] = Field(default_factory=dict)
    relevance_breakdown: Dict[str, Any] = Field(default_factory=dict)
    pull_direction_candidates: List[PullDirectionCandidateSchema]
    total_faces: int
    applicable_faces: List[str] = Field(default_factory=list)
    excluded_faces: List[str] = Field(default_factory=list)
    cavity_faces: List[str]
    core_faces: List[str]
    insufficient_draft_faces: List[str]
    undercut_faces: List[str]
    connected_undercut_regions: List[Dict[str, Any]] = Field(default_factory=list)
    total_surface_area_mm2: float
    cavity_area_mm2: float
    core_area_mm2: float
    undercut_area_mm2: float
    insufficient_draft_area_mm2: float
    projected_area_mm2: float
    estimated_clamping_tonnage: float
    estimated_cavity_pressure_bar: float
    parting_lines: List[PartingCurveSegmentSchema]
    face_details: Dict[str, FaceDraftResultSchema]
    wall_thickness_regions: List[WallThicknessRegionSchema]
    rib_boss_features: List[RibBossFeatureSchema]
    transverse_holes: List[TransverseHoleSchema]
    findings: List[ManufacturingFindingSchema]
    vector_proofs: List[Dict[str, Any]] = Field(default_factory=list)
    sliders: List[SliderActionSchema] = Field(default_factory=list)
    ai_review: AIManufacturingReviewSchema
    moldability_score: float
    epistemic_summary: Dict[str, int]




