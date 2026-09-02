"""Phase 12: Engineering Issue & Recommendation Engine Test Suite.

Tests:
1.  AI observations convert to structured EngineeringIssue objects
2.  Duplicate Claude/Gemini observations are consolidated into consensus issues
3.  Existing feature IDs are accepted
4.  Invalid feature IDs (FEATURE_999) are rejected by Gatekeeper
5.  Existing dimension IDs are accepted
6.  Invalid dimension IDs (D999) are rejected by Gatekeeper
7.  B-Rep entity references are validated against 3D CAD shape
8.  Numerical claims checked against exact OCCT geometry
9.  Structured EngineeringRecommendations generated for validated issues
10. Unsupported recommendation actions are rejected
11. Provider consensus summary generated
12. Provider disagreement / single-provider attribution preserved
13. Human approval state strictly initialized to AWAITING_HUMAN_APPROVAL
14. Approval updates state to APPROVED with ZERO CAD mutation
15. Rejection updates state to REJECTED with ZERO CAD mutation
16. Original .FCStd SHA-256 hash remains 100% unchanged before/after review
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.intelligence.issues import EngineeringIssue, IssueCategory, IssueSeverity, IssueStatus
from src.intelligence.recommendations import EngineeringRecommendation, RecommendationAction, RecommendationStatus
from src.intelligence.issue_engine import EngineeringIssueEngine
from src.intelligence.visual_reviewer import compute_file_sha256

STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
FCSTD_FILE = OUTPUT_DIR / "Pieza18_1_complete_dimensioned.FCStd"


def run_phase12_tests():
    print("=" * 60)
    print("PHASE 12 — ENGINEERING ISSUE & RECOMMENDATION ENGINE TEST SUITE")
    print("=" * 60)

    assert FCSTD_FILE.exists(), f"Source FCStd missing: {FCSTD_FILE}"
    hash_before = compute_file_sha256(FCSTD_FILE)

    engine = EngineeringIssueEngine(STEP_FILE, OUTPUT_DIR)
    summary = engine.process_visual_reviews()

    # 1. AI observations become issues
    print("  [TEST 1] AI observations converted to structured EngineeringIssue objects...")
    assert len(engine.issues) >= 4
    for iss in engine.issues:
        assert isinstance(iss, EngineeringIssue)
        assert iss.issue_id.startswith("ISSUE_")
        assert len(iss.source_providers) >= 1
    print(f"         {len(engine.issues)} structured engineering issues generated ✓")

    # 2. Consolidation of duplicate observations
    print("  [TEST 2] Consolidating shared observations between Claude and Gemini...")
    consensus = summary.get("consensus", {})
    assert consensus["consensus_issues_count"] >= 3
    print(f"         {consensus['consensus_issues_count']} consensus issues consolidated across providers ✓")

    # 3. Existing feature IDs accepted
    print("  [TEST 3] Existing feature IDs verified in CAD model...")
    bore_issue = next((i for i in engine.issues if "BORE_003" in i.affected_feature_ids), None)
    assert bore_issue is not None
    assert bore_issue.deterministic_validation_status == "validated"
    print("         Valid feature ID BORE_003 accepted and validated ✓")

    # 4. Gatekeeper rejects invalid feature IDs
    print("  [TEST 4] Gatekeeper rejects invalid feature IDs (FEATURE_999)...")
    fake_issue = EngineeringIssue(
        issue_id="ISSUE_FAKE",
        title="Fake Issue",
        category=IssueCategory.OTHER,
        severity=IssueSeverity.HIGH,
        description="Fake",
        visual_observation="Fake",
        engineering_reason="Fake",
        affected_feature_ids=["FEATURE_999"],
    )
    status, errors = engine._validate_issue(fake_issue)
    assert status == "rejected"
    assert any("FEATURE_999" in e for e in errors)
    print("         Invalid feature ID FEATURE_999 successfully rejected by Gatekeeper ✓")

    # 5. Existing dimension IDs accepted
    print("  [TEST 5] Existing dimension IDs accepted in candidates...")
    cbore_issue = next((i for i in engine.issues if "D001" in i.affected_dimension_ids), None)
    assert cbore_issue is not None
    assert cbore_issue.deterministic_validation_status == "validated"
    print("         Valid dimension ID D001 accepted and validated ✓")

    # 6. Gatekeeper rejects invalid dimension IDs
    print("  [TEST 6] Gatekeeper rejects invalid dimension IDs (D999)...")
    fake_dim_issue = EngineeringIssue(
        issue_id="ISSUE_FAKE2",
        title="Fake Dim",
        category=IssueCategory.OTHER,
        severity=IssueSeverity.HIGH,
        description="Fake",
        visual_observation="Fake",
        engineering_reason="Fake",
        affected_dimension_ids=["D999"],
    )
    status, errors = engine._validate_issue(fake_dim_issue)
    assert status == "rejected"
    assert any("D999" in e for e in errors)
    print("         Invalid dimension ID D999 successfully rejected by Gatekeeper ✓")

    # 7. B-Rep face references validated
    print("  [TEST 7] B-Rep entity references validated against 3D CAD shape...")
    assert "Face8" in bore_issue.affected_brep_entities
    fake_face_issue = EngineeringIssue(
        issue_id="ISSUE_FAKE3",
        title="Fake Face",
        category=IssueCategory.OTHER,
        severity=IssueSeverity.HIGH,
        description="Fake",
        visual_observation="Fake",
        engineering_reason="Fake",
        affected_brep_entities=["Face999"],
    )
    status, errors = engine._validate_issue(fake_face_issue)
    assert status == "rejected"
    assert any("Face999" in e for e in errors)
    print("         B-Rep entities verified (Face8 valid, Face999 rejected) ✓")

    # 8. Numerical claims checked against OCCT geometry
    print("  [TEST 8] Numerical claims checked against exact OCCT geometry...")
    ev = bore_issue.evidence
    assert ev.get("diameter_mm") == 30.0
    assert abs(ev.get("sweep_angle_deg", 0.0) - 61.32) < 0.1
    print(f"         Deterministic CAD evidence verified: Ø{ev['diameter_mm']:.1f} mm, sweep={ev['sweep_angle_deg']:.2f}° ✓")

    # 9. Recommendations generated
    print("  [TEST 9] Structured EngineeringRecommendations generated...")
    assert len(engine.recommendations) >= 4
    for r in engine.recommendations:
        assert isinstance(r, EngineeringRecommendation)
        assert r.validation_status == "validated"
        assert r.requires_human_approval is True
        assert r.approval_status == RecommendationStatus.AWAITING_HUMAN_APPROVAL
    print(f"         {len(engine.recommendations)} validated recommendations generated ✓")

    # 10. Unsupported actions rejected
    print("  [TEST 10] Unsupported recommendation actions rejected...")
    class BadRec:
        action = type("Action", (), {"value": "HALLUCINATED_ACTION"})()
        affected_entities = []
    status, errors = engine._validate_recommendation(BadRec)  # type: ignore
    assert status == "rejected"
    print("         Unsupported action HALLUCINATED_ACTION rejected ✓")

    # 11. Provider consensus summary
    print("  [TEST 11] Consensus summary generated...")
    assert summary["consensus"]["total_issues_identified"] == len(engine.issues)
    assert summary["consensus"]["human_approval_state"] == "AWAITING_HUMAN_APPROVAL"
    print("         Consensus summary validated ✓")

    # 12. Provider attribution preserved
    print("  [TEST 12] Provider attribution and provenance preserved...")
    for iss in engine.issues:
        assert len(iss.source_models) > 0
    print("         Provider and model provenance verified for all issues ✓")

    # 13. Human approval state strictly AWAITING_HUMAN_APPROVAL
    print("  [TEST 13] Human approval boundary verified...")
    for r in engine.recommendations:
        assert r.approval_status == RecommendationStatus.AWAITING_HUMAN_APPROVAL
    print("         All recommendations stop at AWAITING_HUMAN_APPROVAL ✓")

    # 14. Approve recommendation (No CAD mutation)
    print("  [TEST 14] Approving recommendation REC_001...")
    approved_rec = engine.approve_recommendation("REC_001")
    assert approved_rec is not None
    assert approved_rec.approval_status == RecommendationStatus.APPROVED
    print("         REC_001 approved: approval_status=APPROVED (Zero CAD mutation) ✓")

    # 15. Reject recommendation (No CAD mutation)
    print("  [TEST 15] Rejecting recommendation REC_002...")
    rejected_rec = engine.reject_recommendation("REC_002")
    assert rejected_rec is not None
    assert rejected_rec.approval_status == RecommendationStatus.REJECTED
    print("         REC_002 rejected: approval_status=REJECTED (Zero CAD mutation) ✓")

    # 16. FCStd SHA-256 hash unchanged
    print("  [TEST 16] Verifying original .FCStd SHA-256 hash immutability...")
    hash_after = compute_file_sha256(FCSTD_FILE)
    assert hash_before == hash_after, f"FCStd mutated! Before: {hash_before}, After: {hash_after}"
    print(f"         FCStd SHA-256 match confirmed: {hash_after[:16]}... (100% immutable) ✓")

    # Verify artifacts
    for art in [
        "Pieza18_1_engineering_issues.json",
        "Pieza18_1_engineering_recommendations.json",
        "Pieza18_1_engineering_review_summary.json",
        "Pieza18_1_engineering_review.txt",
    ]:
        p = OUTPUT_DIR / art
        assert p.exists(), f"Missing artifact: {p}"
        print(f"         Artifact confirmed: {art} ({p.stat().st_size:,} bytes) ✓")

    print("=" * 60)
    print("ALL PHASE 12 ENGINEERING ISSUE & RECOMMENDATION TESTS PASSED.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_phase12_tests()
    sys.exit(0 if success else 1)
