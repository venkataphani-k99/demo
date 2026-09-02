"""Decision and review data models and contracts for Engineering Drawing Intelligence.

Designed with zero required external dependencies (uses standard library dataclasses),
ensuring 100% compatibility across both FreeCAD Python and FastAPI environments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EngineeringDecision:
    """Structured decision made by an engineering reasoning agent for a single dimension candidate."""
    dimension_id: str
    decision: str                         # "include" | "exclude" | "defer" | "ambiguous" | "requires_human_review"
    reason: str                           # engineering rationale explaining the decision
    exact_cad_value: float                # exact mathematical measurement verified from CAD kernel
    priority: str = "PRIMARY"             # "PRIMARY" | "SECONDARY" | "OPTIONAL" | "AMBIGUOUS"
    selected_view: Optional[str] = None   # "Front" | "Top" | "Left" | "Right" | "Bottom"
    confidence: float = 1.0               # agent confidence score (0.0 to 1.0)
    source_entities: List[str] = field(default_factory=list)
    source_feature: Optional[str] = None
    measurement_source: str = "OCCT"      # source of geometric measurement truth (always OCCT)
    unit: str = "mm"
    requires_review: bool = False
    review_flags: List[str] = field(default_factory=list)
    validation_status: str = "pending"    # "passed" | "validation_failed"
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass
class VisionReviewResult:
    """Multimodal critique result evaluating rendered drawing presentation."""
    readability: str = "high"             # "high" | "acceptable" | "poor"
    visual_issues: List[str] = field(default_factory=list)
    missing_visible_annotations: List[str] = field(default_factory=list)
    requires_review: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass
class DrawingDecisionSet:
    """Complete collection of engineering decisions for a CAD model."""
    model_file: str
    drawing_file: str
    total_candidates: int
    included_count: int
    excluded_count: int
    deferred_count: int
    ambiguous_count: int
    review_required_count: int
    provider_name: str
    decisions: List[EngineeringDecision]
    vision_review: Optional[VisionReviewResult] = None
    feature_coverages: List[Dict[str, Any]] = field(default_factory=list)
    potential_datums: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_file": self.model_file,
            "drawing_file": self.drawing_file,
            "total_candidates": self.total_candidates,
            "included_count": self.included_count,
            "excluded_count": self.excluded_count,
            "deferred_count": self.deferred_count,
            "ambiguous_count": self.ambiguous_count,
            "review_required_count": self.review_required_count,
            "provider_name": self.provider_name,
            "decisions": [d.to_dict() for d in self.decisions],
            "vision_review": self.vision_review.to_dict() if self.vision_review else None,
            "feature_coverages": self.feature_coverages,
            "potential_datums": self.potential_datums,
        }

    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass
class EngineeringRecommendation:
    """Structured engineering recommendation formulated by an AI model reviewing a CAD drawing."""
    recommendation_id: str
    action: str                           # "include" | "exclude" | "relocate" | "investigate" | "section_view" | "human_review"
    reason: str                           # engineering rationale explaining the recommendation
    dimension_id: Optional[str] = None    # references existing candidate ID or None
    feature_id: Optional[str] = None      # references recognized feature ID or None
    selected_view: Optional[str] = None   # recommended view
    confidence: float = 1.0               # model confidence (0.0 to 1.0)
    requires_human_review: bool = False
    evidence: List[str] = field(default_factory=list)  # DimensionCandidate IDs, Feature IDs, B-Rep entity IDs
    validation_status: str = "pending"    # "passed" | "validation_failed"
    validation_notes: List[str] = field(default_factory=list)
    requires_new_cad_analysis: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass
class EngineeringReview:
    """Comprehensive multimodal engineering review of a CAD model and its 2D drawing."""
    review_id: str
    provider: str
    model: str
    overall_assessment: str               # "good" | "acceptable" | "needs_improvement" | "critical_review_needed"
    good_aspects: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)
    recommendations: List[EngineeringRecommendation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_human_review: bool = False
    stats: Dict[str, Any] = field(default_factory=dict)
    disagreements_with_deterministic: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "provider": self.provider,
            "model": self.model,
            "overall_assessment": self.overall_assessment,
            "good_aspects": self.good_aspects,
            "improvement_areas": self.improvement_areas,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "warnings": self.warnings,
            "requires_human_review": self.requires_human_review,
            "stats": self.stats,
            "disagreements_with_deterministic": self.disagreements_with_deterministic,
        }

    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()
