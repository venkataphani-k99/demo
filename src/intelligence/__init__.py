"""Engineering Drawing Intelligence Layer package."""
from src.intelligence.decision_model import (
    EngineeringDecision,
    DrawingDecisionSet,
    VisionReviewResult,
    EngineeringRecommendation,
    EngineeringReview,
)

try:
    from src.intelligence.tools import CADToolRegistry
    from src.intelligence.providers import (
        EngineeringReasoningProvider,
        MockReasoningProvider,
        ClaudeReasoningProvider,
        GeminiReasoningProvider,
        get_reasoning_provider,
    )
    from src.intelligence.vision_reviewer import DrawingVisionReviewer, MockDrawingVisionReviewer
    from src.intelligence.pipeline import (
        DeterministicValidationGatekeeper,
        EngineeringIntelligencePipeline,
    )
    from src.intelligence.review_engine import EngineeringReviewEngine
except Exception:
    CADToolRegistry = None  # type: ignore
    EngineeringReasoningProvider = None  # type: ignore
    MockReasoningProvider = None  # type: ignore
    ClaudeReasoningProvider = None  # type: ignore
    GeminiReasoningProvider = None  # type: ignore
    get_reasoning_provider = None  # type: ignore
    DrawingVisionReviewer = None  # type: ignore
    MockDrawingVisionReviewer = None  # type: ignore
    DeterministicValidationGatekeeper = None  # type: ignore
    EngineeringIntelligencePipeline = None  # type: ignore
    EngineeringReviewEngine = None  # type: ignore

__all__ = [
    "EngineeringDecision",
    "DrawingDecisionSet",
    "VisionReviewResult",
    "EngineeringRecommendation",
    "EngineeringReview",
    "CADToolRegistry",
    "EngineeringReasoningProvider",
    "MockReasoningProvider",
    "ClaudeReasoningProvider",
    "GeminiReasoningProvider",
    "get_reasoning_provider",
    "DrawingVisionReviewer",
    "MockDrawingVisionReviewer",
    "DeterministicValidationGatekeeper",
    "EngineeringIntelligencePipeline",
    "EngineeringReviewEngine",
]
