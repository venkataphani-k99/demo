"""Phase 22 — AI Reasoning Provider Interface.

Defines the pluggable abstraction for AI reasoning backends (Gemini, Claude, Mock).
Enforces structured output contracts and evidence-constrained analysis.
"""
from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AIEvidenceReference:
    entity_type: str                   # "FACE", "EDGE", "SOLID", "SECTION", "VIEW"
    entity_id: str                     # "Face2", "Edge14", "SEC_AA", "FRONT"
    measured_property: Optional[str] = None # "diameter_mm=23.0", "area=120.5"


@dataclass
class AIFeatureReasoning:
    feature_id: str
    known_geometry: str                # Pure geometric fact from OCCT
    inferred_engineering_role: str     # Semantic role (e.g. "Possible fluid port")
    relevance_category: str            # "CRITICAL", "FUNCTIONAL", "INTERFACE", etc.
    engineering_reasoning: str         # Plain-English technical rationale
    alternative_interpretations: List[str] # Possible alternative functions
    evidence_references: List[AIEvidenceReference]
    confidence_score: float            # 0.0 to 1.0 (Interpretation confidence)
    unknowns_and_assumptions: List[str]
    recommended_engineer_check: str


@dataclass
class AIQuestionAnswer:
    question: str
    answer: str
    grounded_evidence: List[AIEvidenceReference]
    epistemic_qualification: str       # "Grounded in B-Rep geometry", "Inferred", "Not determinable"
    suggested_followups: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIReviewResult:
    provider_name: str
    model_name: str
    executive_part_interpretation: str # Cautious high-level engineering summary
    part_classification: str           # "MECHANICAL_VALVE_ASSEMBLY", "PRISMATIC_BRACKET", "ROTARY_AIRFOIL"
    ranked_feature_interpretations: List[AIFeatureReasoning]
    view_explanations: Dict[str, str]  # view_name -> explanation why it communicates part best
    section_explanations: Dict[str, str] # section_id -> explanation of information gained
    missing_information_analysis: List[str] # Distinguishes not present vs missing
    recommended_engineer_priorities: List[str] # Top 3 items an engineer should inspect first
    raw_ai_response: Optional[str] = None
    validation_status: str = "PENDING"  # "PASSED", "WARNINGS", "REJECTED"
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AIReasoningProvider(abc.ABC):
    """Abstract base class for all AI engineering reasoning providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'gemini', 'claude', 'mock')."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Specific AI model name (e.g. 'gemini-2.5-flash', 'claude-3-5-sonnet')."""
        pass

    @abc.abstractmethod
    def analyze_engineering_evidence(self, evidence_package: Dict[str, Any]) -> AIReviewResult:
        """Perform full evidence-constrained engineering reasoning across the CAD model."""
        pass

    @abc.abstractmethod
    def answer_engineering_question(self, question: str, evidence_package: Dict[str, Any]) -> AIQuestionAnswer:
        """Answer an interactive engineering question strictly grounded in the evidence package."""
        pass
