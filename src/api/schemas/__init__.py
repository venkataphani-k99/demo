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

