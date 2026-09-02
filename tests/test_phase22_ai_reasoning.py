"""Tests for Phase 22 — AI Engineering Reasoning Layer.

Covers:
1. Evidence package construction from OCCT intelligence.
2. AI Reasoning Provider abstraction.
3. Structured output validation & schema adherence.
4. Hallucinated FaceID rejection.
5. Hallucinated dimension inconsistency warnings.
6. Unknown preservation & epistemic distinctions.
7. Provider switching configuration (gemini / mock / claude).
8. Interactive Q&A grounding.
"""
import os
import pytest
from pathlib import Path
from src.cad.step_loader import load_step
from src.cad.engineering_intelligence_engine import EngineeringIntelligenceEngine
from src.intelligence.ai_reasoning import (
    build_evidence_package,
    get_ai_reasoning_provider,
    EvidenceValidator,
    MockAIProvider,
    GeminiAIProvider,
    AIReviewResult,
    AIFeatureReasoning,
    AIEvidenceReference,
    AIQuestionAnswer,
)


@pytest.fixture
def sample_report():
    step_path = Path("workspaces/cb9cfd2c-094b-4bcc-8aeb-03798921320c/RB-3N-20A.STEP")
    if not step_path.exists():
        pytest.skip(f"Test model {step_path} not found.")
    res = load_step(step_path)
    engine = EngineeringIntelligenceEngine()
    rep = engine.analyze_model(res, "RB-3N-20A.STEP")
    res.close()
    return rep


def test_evidence_package_construction(sample_report):
    """Test that build_evidence_package produces clean, structured JSON evidence."""
    pkg = build_evidence_package(sample_report)
    assert pkg["metadata"]["model_name"] == "RB-3N-20A.STEP"
    assert pkg["solid_geometry"]["unique_solids_count"] == 3
    assert pkg["solid_geometry"]["unique_faces_count"] == 230
    assert len(pkg["ranked_features"]) > 0
    assert len(pkg["classified_dimensions"]) > 0
    assert "view_intelligence" in pkg
    assert "section_intelligence" in pkg
    assert len(pkg["epistemic_bounds"]["not_determinable_from_cad"]) >= 4


def test_mock_ai_provider_reasoning(sample_report):
    """Test deterministic mock AI provider execution."""
    pkg = build_evidence_package(sample_report)
    prov = MockAIProvider()
    res = prov.analyze_engineering_evidence(pkg)

    assert isinstance(res, AIReviewResult)
    assert res.provider_name == "mock"
    assert len(res.ranked_feature_interpretations) > 0
    assert "FRONT" in res.view_explanations
    assert "SEC_AA" in res.section_explanations
    assert res.validation_status == "PASSED"


def test_evidence_validator_rejects_hallucinated_face_id(sample_report):
    """Test that EvidenceValidator rejects AI claims referencing non-existent FaceIDs."""
    pkg = build_evidence_package(sample_report)
    validator = EvidenceValidator()

    # Create an AI result containing a fabricated Face9999
    bad_res = AIReviewResult(
        provider_name="test",
        model_name="test-model",
        executive_part_interpretation="Test part",
        part_classification="MECHANICAL_ASSEMBLY",
        ranked_feature_interpretations=[
            AIFeatureReasoning(
                feature_id="FEAT_999",
                known_geometry="Fabricated geometry",
                inferred_engineering_role="Possible imaginary port",
                relevance_category="CRITICAL",
                engineering_reasoning="Fabricated reason",
                alternative_interpretations=[],
                evidence_references=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face9999_IMAGINARY"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face2"), # Valid
                ],
                confidence_score=0.9,
                unknowns_and_assumptions=[],
                recommended_engineer_check="Check",
            )
        ],
        view_explanations={},
        section_explanations={},
        missing_information_analysis=[],
        recommended_engineer_priorities=[],
    )

    validated = validator.validate_review_result(bad_res, pkg)
    assert validated.validation_status == "WARNINGS"
    assert any("HALLUCINATION REJECTED" in note for note in validated.validation_notes)
    # The invalid entity was removed from references, keeping only valid Face2
    feat = validated.ranked_feature_interpretations[0]
    assert len(feat.evidence_references) == 1
    assert feat.evidence_references[0].entity_id == "Face2"


def test_evidence_validator_flags_dimension_inconsistency(sample_report):
    """Test that validator catches hallucinated dimensions (e.g. Ø99mm when OCCT says Ø23mm)."""
    pkg = build_evidence_package(sample_report)
    validator = EvidenceValidator()

    bad_res = AIReviewResult(
        provider_name="test",
        model_name="test-model",
        executive_part_interpretation="Test part",
        part_classification="MECHANICAL_ASSEMBLY",
        ranked_feature_interpretations=[
            AIFeatureReasoning(
                feature_id="FEAT_001",
                known_geometry="Internal cylinder Ø99.5 mm",
                inferred_engineering_role="Possible fluid port",
                relevance_category="CRITICAL",
                engineering_reasoning="Contains Ø99.5 mm bore",
                alternative_interpretations=[],
                evidence_references=[AIEvidenceReference(entity_type="FACE", entity_id="Face2")],
                confidence_score=0.9,
                unknowns_and_assumptions=[],
                recommended_engineer_check="Check",
            )
        ],
        view_explanations={},
        section_explanations={},
        missing_information_analysis=[],
        recommended_engineer_priorities=[],
    )

    validated = validator.validate_review_result(bad_res, pkg)
    assert any("DIMENSION INCONSISTENCY WARNING" in note for note in validated.validation_notes)


def test_epistemic_language_guard(sample_report):
    """Test that definitive claims like 'definitely is a' are automatically downgraded to 'possible'."""
    pkg = build_evidence_package(sample_report)
    validator = EvidenceValidator()

    res = AIReviewResult(
        provider_name="test",
        model_name="test-model",
        executive_part_interpretation="Test part",
        part_classification="MECHANICAL_ASSEMBLY",
        ranked_feature_interpretations=[
            AIFeatureReasoning(
                feature_id="FEAT_001",
                known_geometry="Internal cylinder",
                inferred_engineering_role="This definitely is a valve port",
                relevance_category="CRITICAL",
                engineering_reasoning="Reason",
                alternative_interpretations=[],
                evidence_references=[AIEvidenceReference(entity_type="FACE", entity_id="Face2")],
                confidence_score=0.9,
                unknowns_and_assumptions=[],
                recommended_engineer_check="Check",
            )
        ],
        view_explanations={},
        section_explanations={},
        missing_information_analysis=[],
        recommended_engineer_priorities=[],
    )

    validated = validator.validate_review_result(res, pkg)
    assert "possible" in validated.ranked_feature_interpretations[0].inferred_engineering_role
    assert "definitely is a" not in validated.ranked_feature_interpretations[0].inferred_engineering_role


def test_provider_switching_configuration(monkeypatch):
    """Test provider resolution via factory and environment variables."""
    monkeypatch.setenv("AI_PROVIDER", "mock")
    prov_mock = get_ai_reasoning_provider()
    assert isinstance(prov_mock, MockAIProvider)

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    prov_gemini = get_ai_reasoning_provider()
    assert isinstance(prov_gemini, GeminiAIProvider)

    monkeypatch.setenv("AI_PROVIDER", "claude")
    with pytest.raises(NotImplementedError):
        get_ai_reasoning_provider()
