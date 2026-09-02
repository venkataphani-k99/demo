"""Test Suite for Phase 20 Engineering Design Intelligence & Verification Engine.

Tests:
1. BRepGeometryAuditor deduplication and exact envelope extraction.
2. ViewIntelligenceEngine usefulness scoring and primary/secondary classification.
3. SectionIntelligenceEngine candidate cuts and internal feature exposure scoring.
4. EngineeringIntelligenceEngine answering the 12 core engineering questions with 100% geometric provenance.
"""
from pathlib import Path
import pytest

from src.cad.step_loader import load_step
from src.cad.brep_geometry_auditor import BRepGeometryAuditor
from src.cad.view_intelligence import ViewIntelligenceEngine
from src.cad.section_intelligence import SectionIntelligenceEngine
from src.cad.engineering_intelligence_engine import EngineeringIntelligenceEngine


@pytest.fixture
def rb3n_shape():
    p = Path("workspaces/cb9cfd2c-094b-4bcc-8aeb-03798921320c/RB-3N-20A.STEP")
    if not p.exists():
        pytest.skip(f"RB-3N-20A.STEP not found at {p}")
    res = load_step(p)
    yield res
    res.close()


def test_brep_geometry_auditor_deduplication(rb3n_shape):
    """Test 1: Auditor correctly deduplicates 6 raw solid occurrences to 3 unique solids."""
    auditor = BRepGeometryAuditor()
    audit = auditor.audit_shape(rb3n_shape, "RB-3N-20A.STEP")

    assert audit.total_raw_solids == 6, "Must identify all 6 raw solid instances in compound."
    assert audit.unique_solids_count == 3, "Must deduplicate to exactly 3 unique physical solids."
    assert audit.unique_faces_count == 230, "Unique faces must equal 230 (168+31+31)."
    assert audit.unique_edges_count == 611, "Unique edges must equal 611 (444+80+87)."
    assert audit.assembly_envelope_mm[0] == pytest.approx(114.0, abs=0.1)
    assert audit.assembly_envelope_mm[1] == pytest.approx(71.5, abs=0.1)
    assert audit.assembly_envelope_mm[2] == pytest.approx(56.2, abs=0.1)


def test_view_intelligence_scoring(rb3n_shape):
    """Test 2: View intelligence assigns high scores to Front, Top, Right, Isometric views."""
    view_engine = ViewIntelligenceEngine()
    report = view_engine.analyze_views(rb3n_shape, model_name="RB-3N-20A.STEP")

    assert "FRONT" in report.primary_views
    assert "TOP" in report.primary_views
    assert "RIGHT" in report.primary_views
    assert "ISOMETRIC" in report.primary_views
    assert report.evaluations["FRONT"].usefulness_score >= 0.85
    assert len(report.evaluations["TOP"].engineering_rationale) > 0


def test_section_intelligence_candidates(rb3n_shape):
    """Test 3: Section intelligence generates candidate cuts and scores internal feature exposure."""
    section_engine = SectionIntelligenceEngine()
    report = section_engine.evaluate_sections(rb3n_shape, model_name="RB-3N-20A.STEP")

    assert len(report.candidates) >= 3, "Must generate at least 3 candidate cutting planes."
    assert report.recommended_primary_section == "SEC_AA"
    primary_cand = report.candidates[0]
    assert primary_cand.section_type == "FULL_SECTION"
    assert primary_cand.exposed_feature_count > 0, "Must expose internal cavity/bore features."
    assert primary_cand.usefulness_score >= 0.85


def test_engineering_intelligence_12_questions(rb3n_shape):
    """Test 4: Engineering intelligence engine answers all 12 core questions with geometric truth."""
    engine = EngineeringIntelligenceEngine()
    report = engine.analyze_model(rb3n_shape, "RB-3N-20A.STEP")

    assert len(report.question_answers) == 12, "Must address all 12 core engineering questions."
    assert report.geometric_validation_status == "PASSED"
    assert report.engineering_completeness_score >= 90.0
    assert len(report.feature_graph) >= 5
    assert len(report.classified_dimensions) >= 10

    # Verify four-tier importance classification
    tiers = {d.importance_tier for d in report.classified_dimensions}
    assert "TIER_1_CRITICAL" in tiers
    assert "TIER_2_FUNCTIONAL" in tiers
    assert "TIER_3_ENVELOPE" in tiers

    # Verify provenance on every dimension
    for d in report.classified_dimensions:
        assert d.source_entities, f"Dimension {d.dimension_id} must have source entity provenance."
        assert d.measurement_method.startswith("OCCT_"), f"Dimension {d.dimension_id} must use OCCT measurement method."
