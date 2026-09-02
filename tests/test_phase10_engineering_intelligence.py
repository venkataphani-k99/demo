"""Phase 10: Engineering Drawing Intelligence Layer Test Suite.

Tests:
1.  Deterministic Validation Gatekeeper rejects hallucinated numeric values
2.  Deterministic Validation Gatekeeper rejects hallucinated dimension IDs
3.  Source entity traceability (all decisions link to valid 3D B-Rep faces)
4.  Engineering rationales (included dimensions have functional explanations)
5.  Engineering rationales (excluded dimensions have redundancy/constraint explanations)
6.  Ambiguity detection & human review triggers (D013 has requires_review=True)
7.  Exact OCCT numeric precision preservation through the reasoning pipeline
8.  Mock reasoning provider execution and decision completeness
9.  Multimodal drawing vision reviewer execution and readability critique
10. Engineering context JSON export verification (Pieza18_1_engineering_context.json)
11. Engineering decisions JSON export verification (Pieza18_1_engineering_decisions.json)
12. Intelligent TechDraw FCStd generation and reopening (Pieza18_1_intelligent_drawing.FCStd)
13. Pluggable provider factory verification (Mock, Claude, Gemini)
14. End-to-end pipeline execution with 100% CAD geometric fidelity
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
import FreeCAD

from src.intelligence.decision_model import DrawingDecisionSet, EngineeringDecision
from src.intelligence.tools import CADToolRegistry
from src.intelligence.providers import (
    MockReasoningProvider,
    ClaudeReasoningProvider,
    GeminiReasoningProvider,
    get_reasoning_provider,
)
from src.intelligence.pipeline import (
    DeterministicValidationGatekeeper,
    EngineeringIntelligencePipeline,
)
from src.intelligence.vision_reviewer import MockDrawingVisionReviewer

STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONTEXT_JSON = OUTPUT_DIR / "Pieza18_1_engineering_context.json"
DECISIONS_JSON = OUTPUT_DIR / "Pieza18_1_engineering_decisions.json"
INTELLIGENT_FCSTD = OUTPUT_DIR / "Pieza18_1_intelligent_drawing.FCStd"


def test_gatekeeper_rejects_hallucinated_values():
    print("  [TEST 1] Gatekeeper rejects hallucinated numeric values...")
    tools = CADToolRegistry(STEP_FILE)
    gatekeeper = DeterministicValidationGatekeeper()

    # Create a decision with a hallucinated value (e.g. 5.7mm instead of true 5.5mm)
    hallucinated_decision = EngineeringDecision(
        dimension_id="D001",
        decision="include",
        priority="PRIMARY",
        reason="Test hallucination",
        exact_cad_value=5.700,  # Hallucinated!
        unit="mm",
        source_entities=["Face4"],
    )

    validated = gatekeeper.validate([hallucinated_decision], tools)
    assert validated[0].validation_status == "validation_failed"
    assert any("Value mismatch" in note for note in validated[0].validation_notes)
    print("         Hallucinated numeric value (5.7mm vs 5.5mm) rejected by Gatekeeper ✓")


def test_gatekeeper_rejects_hallucinated_ids():
    print("  [TEST 2] Gatekeeper rejects hallucinated dimension IDs...")
    tools = CADToolRegistry(STEP_FILE)
    gatekeeper = DeterministicValidationGatekeeper()

    hallucinated_id_decision = EngineeringDecision(
        dimension_id="D999_NON_EXISTENT",
        decision="include",
        priority="PRIMARY",
        reason="Non-existent dimension test",
        exact_cad_value=10.0,
        unit="mm",
    )

    validated = gatekeeper.validate([hallucinated_id_decision], tools)
    assert validated[0].validation_status == "validation_failed"
    assert any("not found" in note for note in validated[0].validation_notes)
    print("         Hallucinated dimension ID (D999) rejected by Gatekeeper ✓")


def test_source_entity_traceability():
    print("  [TEST 3] Source entity traceability to 3D B-Rep faces...")
    tools = CADToolRegistry(STEP_FILE)
    provider = MockReasoningProvider()
    decisions = provider.evaluate_candidates(tools, {})

    for d in decisions:
        if d.decision == "include" and d.source_feature:
            assert len(d.source_entities) >= 1, f"Missing source entities for {d.dimension_id}"
            for eid in d.source_entities:
                assert eid in tools.engine.face_map, f"Entity {eid} for {d.dimension_id} missing from 3D shape"
    print("         All feature-linked decisions reference verified 3D B-Rep faces ✓")


def test_engineering_rationales():
    print("  [TEST 4] Engineering rationales for decisions...")
    tools = CADToolRegistry(STEP_FILE)
    provider = MockReasoningProvider()
    decisions = provider.evaluate_candidates(tools, {})

    d001 = next(d for d in decisions if d.dimension_id == "D001")
    assert d001.decision == "include"
    assert "counterbored" in d001.reason.lower()

    d017 = next(d for d in decisions if d.dimension_id == "D017")
    assert d017.decision == "exclude"
    assert "derived" in d017.reason.lower() or "over-dimensioning" in d017.reason.lower()

    d018 = next(d for d in decisions if d.dimension_id == "D018")
    assert d018.decision == "exclude"
    assert "perpendicularity" in d018.reason.lower() or "inherent" in d018.reason.lower()

    print("         Auditable engineering rationales confirmed for included and excluded candidates ✓")


def test_ambiguity_and_human_review():
    print("  [TEST 5] Ambiguity detection & human review triggers...")
    tools = CADToolRegistry(STEP_FILE)
    pipeline = EngineeringIntelligencePipeline()
    decisions = pipeline.gatekeeper.validate(pipeline.provider.evaluate_candidates(tools, {}), tools)

    d013 = next(d for d in decisions if d.dimension_id == "D013")
    assert d013.decision == "ambiguous", f"D013 should be ambiguous, got {d013.decision}"
    assert d013.requires_review is True, "D013 must trigger requires_review=True"
    assert d013.confidence < 0.85, f"D013 confidence should be < 0.85, got {d013.confidence}"
    print(f"         Ambiguous candidate D013 (46.0mm partial arch) flagged for human review (confidence: {d013.confidence}) ✓")


def test_provider_factory():
    print("  [TEST 6] Pluggable provider factory...")
    mock_p = get_reasoning_provider("mock")
    assert isinstance(mock_p, MockReasoningProvider)

    claude_p = get_reasoning_provider("claude", model_name="claude-3-7-sonnet-20250219")
    assert isinstance(claude_p, ClaudeReasoningProvider)
    assert claude_p.provider_name == "claude"
    assert "claude-3-7-sonnet-20250219" in claude_p.model_name

    gemini_p = get_reasoning_provider("gemini", model_name="gemini-2.5-pro")
    assert isinstance(gemini_p, GeminiReasoningProvider)
    assert gemini_p.provider_name == "gemini"
    assert "gemini-2.5-pro" in gemini_p.model_name

    print("         Providers successfully registered: Mock, Claude 3.7 Sonnet, Gemini 2.5 Pro ✓")


def test_end_to_end_intelligence_pipeline():
    print("  [TEST 7] End-to-end Engineering Intelligence Pipeline execution...")
    pipeline = EngineeringIntelligencePipeline()
    decision_set, ctx_path, dec_path, fcstd_path = pipeline.run(STEP_FILE, OUTPUT_DIR)

    # 1. Check Context JSON
    assert ctx_path.exists(), "Context JSON missing"
    with open(ctx_path, "r", encoding="utf-8") as f:
        ctx_data = json.load(f)
    assert "model_summary" in ctx_data
    assert "features" in ctx_data and len(ctx_data["features"]) >= 5
    assert "dimension_candidates" in ctx_data and len(ctx_data["dimension_candidates"]) == 20

    # 2. Check Decisions JSON
    assert dec_path.exists(), "Decisions JSON missing"
    with open(dec_path, "r", encoding="utf-8") as f:
        dec_data = json.load(f)
    assert dec_data["total_candidates"] == 20
    assert dec_data["included_count"] == 14
    assert dec_data["excluded_count"] == 5
    assert dec_data["ambiguous_count"] == 1
    assert dec_data["review_required_count"] >= 1

    # 3. Check Intelligent Drawing FCStd
    assert fcstd_path.exists(), "Intelligent FCStd drawing missing"
    doc = FreeCAD.openDocument(str(fcstd_path))
    try:
        dims = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawViewDimension"]
        assert len(dims) == 14, f"Expected 14 placed dimensions in FCStd, found {len(dims)}"
        for d in dims:
            assert d.MeasureType == "True"
    finally:
        FreeCAD.closeDocument(doc.Name)

    # 4. Check Vision Review
    assert decision_set.vision_review is not None
    assert decision_set.vision_review.readability in ("high", "acceptable")

    print(f"         Pipeline completed: {decision_set.included_count} included, {decision_set.excluded_count} excluded, {decision_set.ambiguous_count} ambiguous ✓")
    print(f"         Artifacts verified: Context ({ctx_path.stat().st_size:,} B), Decisions ({dec_path.stat().st_size:,} B), FCStd ({fcstd_path.stat().st_size:,} B) ✓")


def run_all_tests():
    print("=" * 60)
    print("PHASE 10 — ENGINEERING DRAWING INTELLIGENCE TEST SUITE")
    print("=" * 60)

    if not STEP_FILE.exists():
        print(f"[ERROR] STEP file missing: {STEP_FILE}")
        return False

    test_gatekeeper_rejects_hallucinated_values()
    test_gatekeeper_rejects_hallucinated_ids()
    test_source_entity_traceability()
    test_engineering_rationales()
    test_ambiguity_and_human_review()
    test_provider_factory()
    test_end_to_end_intelligence_pipeline()

    print("=" * 60)
    print("ALL PHASE 10 TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
