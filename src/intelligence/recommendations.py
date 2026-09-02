"""Recommendation Model (Phase 12).

Defines structured engineering recommendations linked to validated issues,
supporting human approval lifecycles and frontend consumption.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RecommendationAction(str, Enum):
    ADD_SECTION_VIEW = "ADD_SECTION_VIEW"
    ADD_DETAIL_VIEW = "ADD_DETAIL_VIEW"
    ADD_DIMENSION = "ADD_DIMENSION"
    MOVE_DIMENSION = "MOVE_DIMENSION"
    ADD_LEADER_LINE = "ADD_LEADER_LINE"
    ADD_DRAWING_NOTE = "ADD_DRAWING_NOTE"
    ADD_DATUM_FEATURE_SYMBOL = "ADD_DATUM_FEATURE_SYMBOL"
    INVESTIGATE = "INVESTIGATE"


class RecommendationStatus(str, Enum):
    REVIEWED = "REVIEWED"
    VALIDATED = "VALIDATED"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


@dataclass
class EngineeringRecommendation:
    """Represents a validated, actionable engineering recommendation requiring human approval."""
    recommendation_id: str
    issue_id: str
    action: RecommendationAction
    rationale: str
    affected_entities: List[str] = field(default_factory=list)
    affected_dimensions: List[str] = field(default_factory=list)
    affected_views: List[str] = field(default_factory=list)
    expected_benefit: str = ""
    validation_status: str = "validated"  # "validated" | "rejected"
    validation_errors: List[str] = field(default_factory=list)
    requires_human_approval: bool = True
    approval_status: RecommendationStatus = RecommendationStatus.AWAITING_HUMAN_APPROVAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "issue_id": self.issue_id,
            "action": self.action.value if isinstance(self.action, RecommendationAction) else str(self.action),
            "rationale": self.rationale,
            "affected_entities": self.affected_entities,
            "affected_dimensions": self.affected_dimensions,
            "affected_views": self.affected_views,
            "expected_benefit": self.expected_benefit,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "requires_human_approval": self.requires_human_approval,
            "approval_status": self.approval_status.value if isinstance(self.approval_status, RecommendationStatus) else str(self.approval_status),
        }
