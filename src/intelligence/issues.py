"""Engineering Issue Model (Phase 12).

Defines structured, auditable engineering issue representations with
deterministic CAD evidence linking and human review boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueCategory(str, Enum):
    MISSING_DIMENSION = "missing_dimension"
    AMBIGUOUS_GEOMETRY = "ambiguous_geometry"
    DRAWING_CLARITY = "drawing_clarity"
    DIMENSION_LAYOUT = "dimension_layout"
    SECTION_VIEW = "section_view"
    DATUM = "datum"
    FEATURE_COMMUNICATION = "feature_communication"
    MANUFACTURING_COMMUNICATION = "manufacturing_communication"
    OTHER = "other"


class IssueSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    REVIEWED = "REVIEWED"
    VALIDATED = "VALIDATED"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


@dataclass
class EngineeringIssue:
    """Represents a validated engineering drawing issue with deterministic CAD evidence."""
    issue_id: str
    title: str
    category: IssueCategory
    severity: IssueSeverity
    description: str
    visual_observation: str
    engineering_reason: str
    source_providers: List[str] = field(default_factory=list)
    source_models: List[str] = field(default_factory=list)
    affected_view: Optional[str] = None
    affected_feature_ids: List[str] = field(default_factory=list)
    affected_dimension_ids: List[str] = field(default_factory=list)
    affected_brep_entities: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    deterministic_validation_status: str = "validated"  # "validated" | "rejected"
    validation_errors: List[str] = field(default_factory=list)
    recommendation_ids: List[str] = field(default_factory=list)
    human_review_required: bool = True
    status: IssueStatus = IssueStatus.AWAITING_HUMAN_APPROVAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "title": self.title,
            "category": self.category.value if isinstance(self.category, IssueCategory) else str(self.category),
            "severity": self.severity.value if isinstance(self.severity, IssueSeverity) else str(self.severity),
            "description": self.description,
            "visual_observation": self.visual_observation,
            "engineering_reason": self.engineering_reason,
            "source_providers": self.source_providers,
            "source_models": self.source_models,
            "affected_view": self.affected_view,
            "affected_feature_ids": self.affected_feature_ids,
            "affected_dimension_ids": self.affected_dimension_ids,
            "affected_brep_entities": self.affected_brep_entities,
            "evidence": self.evidence,
            "deterministic_validation_status": self.deterministic_validation_status,
            "validation_errors": self.validation_errors,
            "recommendation_ids": self.recommendation_ids,
            "human_review_required": self.human_review_required,
            "status": self.status.value if isinstance(self.status, IssueStatus) else str(self.status),
        }
