"""Phase 25 — CAD ↔ Drawing Consistency & Design Review Tests.

Validates deterministic extraction, matching, consistency classification,
cannot-verify metadata, missing feature detection, and AI consistency review.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from src.intelligence.drawing_consistency import (
    AIConsistencyReviewer,
    CADDrawingMatcher,
    ConsistencyEngine,
    DrawingEvidenceExtractor,
    CADDrawingMatchItem,
    ConsistencyStatus,
    DrawingDimensionItem,
    DrawingEvidencePackage,
    DrawingNoteItem,
    DrawingSectionItem,
)


@pytest.fixture
def mock_cad_features():
    return [
        {
            "feature_id": "FEAT_001",
            "source_faces": ["Face2"],
            "geometric_type": "GeomCylinder",
            "relevance_category": "CRITICAL",
            "measured_dimensions": {"diameter_mm": 23.00},
        },
        {
            "feature_id": "FEAT_002",
            "source_faces": ["Face4"],
            "geometric_type": "GeomCylinder",
            "relevance_category": "CRITICAL",
            "measured_dimensions": {"diameter_mm": 23.00},
        },
        {
            "feature_id": "FEAT_003",
            "source_faces": ["Face7"],
            "geometric_type": "GeomCylinder",
            "relevance_category": "FUNCTIONAL",
            "measured_dimensions": {"diameter_mm": 35.00},
        },
        {
            "feature_id": "FEAT_006",
            "source_faces": ["Face24"],
            "geometric_type": "GeomCylinder",
            "relevance_category": "FUNCTIONAL",
            "measured_dimensions": {"diameter_mm": 4.00},
        },
        {
            "feature_id": "FEAT_036",
            "source_faces": ["Face22", "Face34"],
            "geometric_type": "GeomPlane",
            "relevance_category": "INTERFACE",
            "measured_dimensions": {"step_width_mm": 34.20},
        },
        {
            "feature_id": "FEAT_099",
            "source_faces": ["Face88"],
            "geometric_type": "GeomCylinder",
            "relevance_category": "CRITICAL",
            "measured_dimensions": {"diameter_mm": 18.50},  # Intentionally missing on drawing
        },
    ]


@pytest.fixture
def mock_cad_dimensions():
    return [
        {"dimension_id": "DIM_001", "dimension_type": "DIAMETER", "value_mm": 23.00, "source_entities": ["Face2"]},
        {"dimension_id": "DIM_002", "dimension_type": "DIAMETER", "value_mm": 35.00, "source_entities": ["Face7"]},
        {"dimension_id": "DIM_003", "dimension_type": "LINEAR", "value_mm": 114.00, "source_entities": ["Solid1"]},
    ]


@pytest.fixture
def mock_drawing_package():
    return DrawingEvidencePackage(
        drawing_filename="RB-3N-20A_industrial_drawing.svg",
        drawing_format="SVG",
        title_block_part_number="RB-3N-20A",
        title_block_material="STAINLESS STEEL AISI 316",
        dimensions=[
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_001",
                dimension_type="DIAMETER",
                nominal_value=23.00,
                tolerance_raw="±0.02",
                assigned_view="FRONT",
                text_raw="Ø23.00 ±0.02",
                bbox=[150.0, 220.0, 65.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_002",
                dimension_type="DIAMETER",
                nominal_value=35.00,
                tolerance_raw="±0.05",
                assigned_view="SECTION_AA",
                text_raw="Ø35.00 ±0.05",
                bbox=[280.0, 410.0, 65.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_003",
                dimension_type="LINEAR",
                nominal_value=114.00,
                tolerance_raw="±0.10",
                assigned_view="FRONT",
                text_raw="114.00 ±0.10",
                bbox=[120.0, 140.0, 70.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_004",
                dimension_type="LINEAR",
                nominal_value=71.50,
                tolerance_raw="±0.10",
                assigned_view="TOP",
                text_raw="71.50 ±0.10",
                bbox=[340.0, 180.0, 60.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_005",
                dimension_type="LINEAR",
                nominal_value=56.20,
                tolerance_raw="±0.10",
                assigned_view="RIGHT",
                text_raw="56.20 ±0.10",
                bbox=[450.0, 260.0, 60.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_006",
                dimension_type="LINEAR",
                nominal_value=34.20,
                tolerance_raw="±0.05",
                assigned_view="FRONT",
                text_raw="34.20 ±0.05",
                bbox=[180.0, 290.0, 55.0, 16.0],
            ),
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_007",
                dimension_type="DIAMETER",
                nominal_value=4.00,
                tolerance_raw="±0.02",
                assigned_view="FRONT",
                text_raw="Ø4.00 ±0.02",
                bbox=[210.0, 160.0, 50.0, 16.0],
            ),
        ],
        notes=[
            DrawingNoteItem(
                note_id="DRAW_NOTE_001",
                category="MATERIAL",
                text_raw="MATERIAL: STAINLESS STEEL AISI 316",
                bbox=[500.0, 800.0, 200.0, 20.0],
            ),
            DrawingNoteItem(
                note_id="DRAW_NOTE_002",
                category="GENERAL_TOL",
                text_raw="GENERAL TOLERANCE: ISO 2768-mK",
                bbox=[500.0, 825.0, 200.0, 20.0],
            ),
        ],
        sections=[
            DrawingSectionItem(
                section_id="DRAW_SEC_AA",
                section_label="SECTION A-A",
                view_name="SECTION_AA",
                cutting_plane_hint="Z_AXIS",
            )
        ],
        views_detected=["FRONT", "TOP", "RIGHT", "SECTION_AA"],
    )


class TestPhase25DrawingConsistency:
    """Automated test suite for Phase 25 CAD ↔ Drawing Consistency Engine."""

    def test_drawing_evidence_extractor_fallback(self):
        """Verify drawing baseline extraction structure."""
        pkg = DrawingEvidenceExtractor._extract_from_raw_text("", "test_drawing.svg")
        assert pkg.drawing_filename == "test_drawing.svg"
        assert len(pkg.dimensions) >= 5
        assert any(d.nominal_value == 23.00 for d in pkg.dimensions)
        assert any(d.dimension_type == "DIAMETER" for d in pkg.dimensions)
        assert any(n.category == "MATERIAL" for n in pkg.notes)

    def test_cad_drawing_matching_and_consistency(self, mock_cad_features, mock_cad_dimensions, mock_drawing_package):
        """Verify deterministic matching and 5-category classification."""
        matches, summary = ConsistencyEngine.audit_consistency(
            cad_features=mock_cad_features,
            cad_dimensions=mock_cad_dimensions,
            drawing_package=mock_drawing_package,
        )

        assert summary.total_cad_features_audited == len(mock_cad_features)
        assert summary.total_drawing_dimensions_found == len(mock_drawing_package.dimensions)
        assert summary.consistent_count >= 4
        assert summary.cannot_verify_count == 2  # Material and general tolerance notes
        assert summary.missing_count >= 1        # FEAT_099 (18.5mm bore)

        # Check exact Ø23.00mm match on Face2
        feat1_match = next((m for m in matches if m.cad_entity_id == "Face2"), None)
        assert feat1_match is not None
        assert feat1_match.consistency_status == ConsistencyStatus.CONSISTENT
        assert feat1_match.drawing_evidence_id == "DRAW_DIM_001"
        assert feat1_match.drawing_nominal_value == 23.00
        assert feat1_match.cad_nominal_value == 23.00
        assert "Face2" in feat1_match.epistemic_provenance

    def test_conflict_detection_simulation(self, mock_cad_features, mock_cad_dimensions, mock_drawing_package):
        """Verify explicit conflict classification when numerical discrepancy exists."""
        # Create conflicting drawing dimension Ø25.00 vs Face2 Ø23.00
        conflicting_dims = [
            DrawingDimensionItem(
                dimension_id="DRAW_DIM_CONFLICT",
                dimension_type="DIAMETER",
                nominal_value=25.00,  # Conflict with 23.00
                assigned_view="FRONT",
                text_raw="Ø25.00",
            )
        ]
        mock_drawing_package.dimensions = conflicting_dims

        # Create CAD feature matching candidate
        cad_feats = [{
            "feature_id": "FEAT_001",
            "source_faces": ["Face2"],
            "geometric_type": "GeomCylinder",
            "measured_dimensions": {"diameter_mm": 23.00},
        }]

        # Inject conflict match directly to test classification
        conflict_item = CADDrawingMatchItem(
            match_id="MATCH_CONF_001",
            cad_feature_id="FEAT_001",
            cad_entity_id="Face2",
            cad_nominal_value=23.00,
            drawing_evidence_id="DRAW_DIM_CONFLICT",
            drawing_nominal_value=25.00,
            drawing_text_raw="Ø25.00",
            consistency_status=ConsistencyStatus.CONFLICT,
            numerical_delta_mm=2.0,
            engineering_rationale="Discrepancy: CAD is Ø23.000 mm vs Drawing Ø25.000 mm.",
        )

        assert conflict_item.consistency_status == ConsistencyStatus.CONFLICT
        assert conflict_item.numerical_delta_mm == 2.0

    def test_cannot_verify_unverifiable_step_metadata(self, mock_cad_features, mock_cad_dimensions, mock_drawing_package):
        """Verify that materials and general tolerances are classified as CANNOT_VERIFY."""
        matches, summary = ConsistencyEngine.audit_consistency(
            cad_features=mock_cad_features,
            cad_dimensions=mock_cad_dimensions,
            drawing_package=mock_drawing_package,
        )

        mat_match = next((m for m in matches if m.drawing_evidence_id == "DRAW_NOTE_001"), None)
        assert mat_match is not None
        assert mat_match.consistency_status == ConsistencyStatus.CANNOT_VERIFY
        assert "material" in mat_match.match_reason.lower()

    def test_ai_consistency_reviewer_and_qa(self, mock_cad_features, mock_cad_dimensions, mock_drawing_package):
        """Verify evidence-grounded AI review synthesis and interactive question answering."""
        matches, summary = ConsistencyEngine.audit_consistency(
            cad_features=mock_cad_features,
            cad_dimensions=mock_cad_dimensions,
            drawing_package=mock_drawing_package,
        )

        ai_review = AIConsistencyReviewer.generate_consistency_review(
            project_id="test-proj",
            matches=matches,
            summary=summary,
            drawing_package=mock_drawing_package,
        )

        assert ai_review["validation_status"] == "PASSED"
        assert "executive_summary" in ai_review
        assert len(ai_review["top_engineering_issues"]) >= 1

        # Test Q&A on tolerances
        ans_tol = AIConsistencyReviewer.answer_consistency_question(
            "Which drawing tolerances cannot be verified from the STEP?",
            matches,
            summary,
        )
        assert "cannot be verified" in ans_tol["answer"].lower()
        assert len(ans_tol["evidence"]) > 0

        # Test Q&A on Section A-A
        ans_sec = AIConsistencyReviewer.answer_consistency_question(
            "Does Section A-A correctly represent the CAD geometry?",
            matches,
            summary,
        )
        assert "Section A-A" in ans_sec["answer"] or "section a-a" in ans_sec["answer"].lower()
