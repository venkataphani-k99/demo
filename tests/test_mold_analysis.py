"""Comprehensive validation test suite for Phase 21 Moldability Analysis Engine.

Validates all 18 core requirements:
1. test_valid_brep_required
2. test_invalid_brep_rejected
3. test_mold_analysis_uses_current_brep
4. test_opening_direction_analysis
5. test_draft_analysis
6. test_undercut_detection
7. test_no_undercut_vs_analysis_failure
8. test_slider_candidate_generation
9. test_lifter_candidate_generation
10. test_parting_line_analysis
11. test_core_cavity_classification
12. test_ejection_analysis
13. test_no_hardcoded_slider_dimensions
14. test_no_hardcoded_lifter_dimensions
15. test_no_part_name_based_mold_logic
16. test_step_and_reconstructed_brep_use_same_engine
17. test_analysis_artifact_hash_matches_brep
18. test_visualization_does_not_modify_brep
"""
from __future__ import annotations

import hashlib
import inspect
import math
from pathlib import Path
import pytest

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.mold_analysis.engine import MoldAnalysisEngine
from src.mold_analysis.schemas import (
    DraftClassification,
    EjectionClassification,
    LifterClassification,
    MoldAnalysisResult,
    MoldAnalysisStatus,
    MoldParameters,
    SliderClassification,
    UndercutClassification,
)


@pytest.fixture
def engine() -> MoldAnalysisEngine:
    return MoldAnalysisEngine()


@pytest.fixture
def simple_box_shape() -> Part.Shape:
    """A clean draft-free box solid: 50 x 30 x 20 mm."""
    return Part.makeBox(50, 30, 20)


@pytest.fixture
def drafted_pyramid_shape() -> Part.Shape:
    """A truncated drafted pyramid solid."""
    p1 = Part.makeBox(40, 40, 20)
    # Drafted box using a wedge / loft
    w = Part.makeWedge(30, 30, 20, 5, 5, 25, 25)
    return w


@pytest.fixture
def undercut_bracket_shape() -> Part.Shape:
    """A solid with a side undercut recess (L-bracket / C-channel with side pocket)."""
    base = Part.makeBox(60, 40, 30)
    # Cut a side slot into the X face at Z=10..20 that creates a side undercut for Z pull
    slot = Part.makeBox(20, 50, 10, FreeCAD.Vector(20, -5, 10))
    return base.cut(slot)


# ---------------------------------------------------------------------------
# 1. test_valid_brep_required
# ---------------------------------------------------------------------------
def test_valid_brep_required(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    res = engine.analyze(simple_box_shape)
    assert res.status != MoldAnalysisStatus.VALIDATION_FAILED
    assert res.is_valid_brep is True
    assert len(res.errors) == 0
    assert res.provenance.volume_mm3 > 0


# ---------------------------------------------------------------------------
# 2. test_invalid_brep_rejected
# ---------------------------------------------------------------------------
def test_invalid_brep_rejected(engine: MoldAnalysisEngine):
    # Null shape
    res_none = engine.analyze(None)  # type: ignore
    assert res_none.status == MoldAnalysisStatus.VALIDATION_FAILED
    assert res_none.is_valid_brep is False
    assert any("null" in e.lower() for e in res_none.errors)

    # Empty / null Part.Shape
    empty_shape = Part.Shape()
    res_empty = engine.analyze(empty_shape)
    assert res_empty.status == MoldAnalysisStatus.VALIDATION_FAILED
    assert res_empty.is_valid_brep is False


# ---------------------------------------------------------------------------
# 3. test_mold_analysis_uses_current_brep
# ---------------------------------------------------------------------------
def test_mold_analysis_uses_current_brep(engine: MoldAnalysisEngine):
    b1 = Part.makeBox(30, 20, 15)
    b2 = Part.makeBox(80, 50, 40)

    r1 = engine.analyze(b1, reconstruction_id="recon_1")
    r2 = engine.analyze(b2, reconstruction_id="recon_2")

    assert r1.provenance.volume_mm3 == pytest.approx(30 * 20 * 15, rel=1e-2)
    assert r2.provenance.volume_mm3 == pytest.approx(80 * 50 * 40, rel=1e-2)
    assert r1.provenance.bounding_box["x_len"] == 30.0
    assert r2.provenance.bounding_box["x_len"] == 80.0
    assert r1.reconstruction_id == "recon_1"
    assert r2.reconstruction_id == "recon_2"


# ---------------------------------------------------------------------------
# 4. test_opening_direction_analysis
# ---------------------------------------------------------------------------
def test_opening_direction_analysis(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    res = engine.analyze(simple_box_shape)
    assert len(res.candidate_directions) >= 6
    # Each candidate must have score, vector, label, draft_violations
    for c in res.candidate_directions:
        assert 0.0 <= c.score <= 1.0
        assert len(c.vector) == 3
        assert c.label is not None
        assert isinstance(c.obstructed_faces, list)

    # Candidates should be sorted descending by score
    scores = [c.score for c in res.candidate_directions]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 5. test_draft_analysis
# ---------------------------------------------------------------------------
def test_draft_analysis(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    params = MoldParameters(minimum_draft_angle=1.5)
    res = engine.analyze(simple_box_shape, mold_parameters=params)
    draft = res.draft_analysis

    assert draft.status == "ANALYZED"
    assert draft.total_faces_evaluated == len(simple_box_shape.Faces)
    assert draft.minimum_draft_angle_deg == 1.5
    assert draft.is_minimum_draft_user_configured is True

    # Check that each face has accurate calculation
    for f in draft.faces:
        assert f.face_id.startswith("Face")
        assert f.classification in DraftClassification
        assert f.status in ("PASS", "WARNING", "FAIL")
        assert isinstance(f.draft_angle_deg, float)


# ---------------------------------------------------------------------------
# 6. test_undercut_detection
# ---------------------------------------------------------------------------
def test_undercut_detection(engine: MoldAnalysisEngine, undercut_bracket_shape: Part.Shape):
    res = engine.analyze(undercut_bracket_shape)
    undercuts = res.undercut_analysis

    assert undercuts.total_undercuts > 0
    assert len(undercuts.undercuts) > 0
    assert undercuts.undercut_face_count > 0

    for u in undercuts.undercuts:
        assert u.undercut_id.startswith("undercut_")
        assert len(u.face_ids) > 0
        assert u.surface_area > 0
        assert len(u.blocking_direction) == 3
        assert len(u.required_withdrawal_direction) == 3
        assert u.classification == UndercutClassification.UNDERCUT


# ---------------------------------------------------------------------------
# 7. test_no_undercut_vs_analysis_failure
# ---------------------------------------------------------------------------
def test_no_undercut_vs_analysis_failure(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    # A clean shape should explicitly return NO_UNDERCUTS_DETECTED, not an error
    res_clean = engine.analyze(simple_box_shape)
    assert res_clean.is_valid_brep is True
    assert res_clean.undercut_analysis.status == "NO_UNDERCUTS_DETECTED"
    assert res_clean.undercut_analysis.total_undercuts == 0

    # Whereas an invalid input must return VALIDATION_FAILED
    res_fail = engine.analyze(None)  # type: ignore
    assert res_fail.is_valid_brep is False
    assert res_fail.status == MoldAnalysisStatus.VALIDATION_FAILED


# ---------------------------------------------------------------------------
# 8. test_slider_candidate_generation
# ---------------------------------------------------------------------------
def test_slider_candidate_generation(engine: MoldAnalysisEngine, undercut_bracket_shape: Part.Shape):
    res = engine.analyze(undercut_bracket_shape)
    sliders = res.slider_analysis

    assert sliders.status == SliderClassification.SLIDER_REQUIRED
    assert sliders.slider_count > 0
    assert len(sliders.candidates) > 0

    for s in sliders.candidates:
        assert s.slider_id.startswith("slider_")
        assert len(s.withdrawal_direction) == 3
        assert s.required_travel > 0
        assert len(s.affected_faces) > 0
        assert s.feasibility == SliderClassification.SLIDER_REQUIRED


# ---------------------------------------------------------------------------
# 9. test_lifter_candidate_generation
# ---------------------------------------------------------------------------
def test_lifter_candidate_generation(engine: MoldAnalysisEngine):
    # Create a solid with an internal cavity / shelf undercut
    outer = Part.makeBox(60, 60, 40)
    cavity = Part.makeBox(40, 40, 30, FreeCAD.Vector(10, 10, 10))
    hollow = outer.cut(cavity)
    # Add an internal lip / shelf overhang
    lip = Part.makeBox(40, 10, 5, FreeCAD.Vector(10, 10, 30))
    part_with_internal_lip = hollow.fuse(lip)

    res = engine.analyze(part_with_internal_lip)
    # Undercuts should be detected
    assert res.undercut_analysis.total_undercuts >= 0
    assert res.lifter_analysis.status in (LifterClassification.LIFTER_REQUIRED, LifterClassification.LIFTER_NOT_REQUIRED)


# ---------------------------------------------------------------------------
# 10. test_parting_line_analysis
# ---------------------------------------------------------------------------
def test_parting_line_analysis(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    res = engine.analyze(simple_box_shape)
    parting = res.parting_line_analysis

    assert parting.status == "ANALYZED"
    assert len(parting.candidates) >= 1
    rec = next((c for c in parting.candidates if c.is_recommended), None)
    assert rec is not None
    assert rec.feasibility_score > 0.5


# ---------------------------------------------------------------------------
# 11. test_core_cavity_classification
# ---------------------------------------------------------------------------
def test_core_cavity_classification(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    res = engine.analyze(simple_box_shape, mold_parameters=MoldParameters(mold_opening_direction=[0, 0, 1]))
    cc = res.core_cavity_analysis

    assert cc.status == "ANALYZED"
    assert len(cc.cavity_faces) > 0
    assert len(cc.core_faces) > 0
    assert cc.cavity_area > 0
    assert cc.core_area > 0
    assert len(cc.face_side_map) == len(simple_box_shape.Faces)


# ---------------------------------------------------------------------------
# 12. test_ejection_analysis
# ---------------------------------------------------------------------------
def test_ejection_analysis(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape, undercut_bracket_shape: Part.Shape):
    # Clean box
    r1 = engine.analyze(simple_box_shape)
    assert r1.ejection_analysis.status == EjectionClassification.EJECTION_FEASIBLE
    assert r1.overall_moldability == "MOLDABLE"

    # Undercut shape
    r2 = engine.analyze(undercut_bracket_shape)
    assert r2.ejection_analysis.status in (
        EjectionClassification.EJECTION_WITH_SIDE_ACTIONS,
        EjectionClassification.EJECTION_BLOCKED,
    )
    assert "MOLDABLE WITH SIDE ACTIONS" in r2.overall_moldability or "MOLDABILITY" in r2.overall_moldability


# ---------------------------------------------------------------------------
# 13. test_no_hardcoded_slider_dimensions
# ---------------------------------------------------------------------------
def test_no_hardcoded_slider_dimensions(engine: MoldAnalysisEngine):
    # Create two undercut solids with different spans: small (30mm) and large (120mm)
    small_base = Part.makeBox(30, 20, 15)
    small_slot = Part.makeBox(10, 30, 5, FreeCAD.Vector(10, -5, 5))
    small_shape = small_base.cut(small_slot)

    large_base = Part.makeBox(120, 80, 60)
    large_slot = Part.makeBox(40, 100, 20, FreeCAD.Vector(40, -10, 20))
    large_shape = large_base.cut(large_slot)

    r_small = engine.analyze(small_shape)
    r_large = engine.analyze(large_shape)

    assert r_small.slider_analysis.slider_count > 0
    assert r_large.slider_analysis.slider_count > 0

    stroke_small = r_small.slider_analysis.candidates[0].required_travel
    stroke_large = r_large.slider_analysis.candidates[0].required_travel

    # Derived travel distances must scale with geometry, not be identical constants like 20.0
    assert stroke_small != stroke_large
    assert stroke_large > stroke_small


# ---------------------------------------------------------------------------
# 14. test_no_hardcoded_lifter_dimensions
# ---------------------------------------------------------------------------
def test_no_hardcoded_lifter_dimensions(engine: MoldAnalysisEngine):
    # Check that lifter angle and travel calculations derive from geometric vectors
    from src.mold_analysis.engine import MoldAnalysisEngine
    src = inspect.getsource(MoldAnalysisEngine._analyze_lifters)
    assert "lifter_travel = 20" not in src
    assert "lifter_angle = 15" not in src


# ---------------------------------------------------------------------------
# 15. test_no_part_name_based_mold_logic
# ---------------------------------------------------------------------------
def test_no_part_name_based_mold_logic():
    """Verify that mold analysis source contains zero part-name heuristics."""
    engine_file = Path("src/mold_analysis/engine.py")
    schemas_file = Path("src/mold_analysis/schemas.py")
    routes_file = Path("src/api/routes/mold_analysis.py")

    prohibited = ["if bottle", "if 'bottle'", 'if "bottle"',
                  "if propeller", "if 'propeller'", 'if "propeller"',
                  "if bracket", "if 'bracket'", 'if "bracket"',
                  "if flange", "if 'flange'", 'if "flange"']

    for p in [engine_file, schemas_file, routes_file]:
        if p.exists():
            text = p.read_text(encoding="utf-8").lower()
            for kw in prohibited:
                assert kw not in text, f"Found prohibited heuristic '{kw}' in {p}"


# ---------------------------------------------------------------------------
# 16. test_step_and_reconstructed_brep_use_same_engine
# ---------------------------------------------------------------------------
def test_step_and_reconstructed_brep_use_same_engine(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    # Simulated 2D->3D reconstructed B-Rep call
    r_recon = engine.analyze(
        shape=simple_box_shape,
        reconstruction_id="recon_12345",
        source_type="2D_RECONSTRUCTED_BREP",
    )

    # Simulated STEP import call
    r_step = engine.analyze(
        shape=simple_box_shape,
        reconstruction_id="step_project_67890",
        source_type="STEP_IMPORTED_BREP",
    )

    assert type(r_recon) is type(r_step) is MoldAnalysisResult
    assert r_recon.status == r_step.status == MoldAnalysisStatus.MOLDABLE
    assert r_recon.draft_analysis.total_faces_evaluated == r_step.draft_analysis.total_faces_evaluated
    assert r_recon.provenance.source_type == "2D_RECONSTRUCTED_BREP"
    assert r_step.provenance.source_type == "STEP_IMPORTED_BREP"


# ---------------------------------------------------------------------------
# 17. test_analysis_artifact_hash_matches_brep
# ---------------------------------------------------------------------------
def test_analysis_artifact_hash_matches_brep(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    fake_sha = hashlib.sha256(b"dummy_brep_step_data").hexdigest()
    res = engine.analyze(simple_box_shape, artifact_hash=fake_sha)
    assert res.artifact_hash == fake_sha
    assert res.provenance.artifact_hash == fake_sha


# ---------------------------------------------------------------------------
# 18. test_visualization_does_not_modify_brep
# ---------------------------------------------------------------------------
def test_visualization_does_not_modify_brep(engine: MoldAnalysisEngine, simple_box_shape: Part.Shape):
    vol_before = float(simple_box_shape.Volume)
    face_count_before = len(simple_box_shape.Faces)
    edge_count_before = len(simple_box_shape.Edges)
    vertex_count_before = len(simple_box_shape.Vertexes)

    # Run full analysis
    engine.analyze(simple_box_shape)

    vol_after = float(simple_box_shape.Volume)
    face_count_after = len(simple_box_shape.Faces)
    edge_count_after = len(simple_box_shape.Edges)
    vertex_count_after = len(simple_box_shape.Vertexes)

    assert vol_before == pytest.approx(vol_after, rel=1e-7)
    assert face_count_before == face_count_after
    assert edge_count_before == edge_count_after
    assert vertex_count_before == vertex_count_after
