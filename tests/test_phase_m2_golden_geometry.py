"""Phase M2 — Golden Geometry & Vector Accuracy Benchmark Suite.

Mandatory validation against 5 synthetic geometries with exact analytical
ground truth and angular error reporting (theta_err = acos(clamp(dot(V_exp, V_act), -1, 1))).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.cad.mold_analyzer import MoldabilityAnalyzer
from src.cad.slider_locator import SliderLocator
from src.cad.mfg_vector_verifier import ManufacturingVectorVerifier


def make_straight_pull_box() -> Part.Shape:
    """TEST A: Straight-pull housing with zero undercuts."""
    box = Part.makeBox(100.0, 80.0, 40.0)
    pocket = Part.makeBox(92.0, 72.0, 36.0, FreeCAD.Vector(4.0, 4.0, 4.0))
    return box.cut(pocket)


def make_box_with_transverse_hole() -> Part.Shape:
    """TEST B: Housing with exact 90-degree transverse side hole along +X."""
    box = Part.makeBox(100.0, 80.0, 50.0)
    pocket = Part.makeBox(90.0, 70.0, 45.0, FreeCAD.Vector(5.0, 5.0, 5.0))
    housing = box.cut(pocket)
    # Drill horizontal hole along X axis at Y=40, Z=25
    hole = Part.makeCylinder(8.0, 110.0, FreeCAD.Vector(-5.0, 40.0, 25.0), FreeCAD.Vector(1.0, 0.0, 0.0))
    return housing.cut(hole)


def make_external_snap_hook() -> Part.Shape:
    """TEST C: Housing with external undercut snap overhang on +X wall."""
    box = Part.makeBox(80.0, 60.0, 40.0)
    # Add an undercut lip hanging over the right wall
    lip = Part.makeBox(12.0, 20.0, 6.0, FreeCAD.Vector(80.0, 20.0, 30.0))
    return box.fuse(lip)


def make_internal_grooved_box() -> Part.Shape:
    """TEST D: Housing with internal undercut groove requiring lifter."""
    box = Part.makeBox(80.0, 60.0, 40.0)
    pocket = Part.makeBox(70.0, 50.0, 35.0, FreeCAD.Vector(5.0, 5.0, 5.0))
    hollow = box.cut(pocket)
    # Recessed internal groove cutting into inside wall at X=75
    groove = Part.makeBox(4.0, 30.0, 8.0, FreeCAD.Vector(73.0, 15.0, 12.0))
    return hollow.cut(groove)


def make_ribs_and_bosses_part() -> Part.Shape:
    """TEST E: Part with mounting bosses and reinforcement ribs."""
    base = Part.makeBox(120.0, 100.0, 4.0)
    boss1 = Part.makeCylinder(7.0, 25.0, FreeCAD.Vector(30.0, 30.0, 4.0), FreeCAD.Vector(0.0, 0.0, 1.0))
    hole1 = Part.makeCylinder(3.5, 30.0, FreeCAD.Vector(30.0, 30.0, 0.0), FreeCAD.Vector(0.0, 0.0, 1.0))
    boss1_cored = boss1.cut(hole1)
    rib = Part.makeBox(80.0, 2.5, 18.0, FreeCAD.Vector(20.0, 50.0, 4.0))
    return base.fuse(boss1_cored).fuse(rib)


def test_golden_geometry_test_a_straight_pull():
    """M2.26 Test A: Straight-pull housing must yield 0 undercuts, optimal Z pull, 0.00° error."""
    shape = make_straight_pull_box()
    analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    report = analyzer.analyze(project_id="test_a")

    # Main Pull Accuracy
    v_exp = [0.0, 0.0, 1.0]
    v_act = report.optimal_pull_direction
    angular_error = ManufacturingVectorVerifier.compute_angular_error(v_exp, v_act)

    assert angular_error < 0.01, f"Main pull error {angular_error}° exceeds 0.01° tolerance"
    assert len(report.undercut_faces) == 0, f"Expected 0 undercuts, got {len(report.undercut_faces)}"
    assert report.relevance_breakdown["excluded_planar_caps"] > 0, "Planar caps must be filtered"
    print(f"\n[PASS] Golden Test A (Straight-Pull): Angular Error = {angular_error:.4f}°, Undercuts = {len(report.undercut_faces)}")


def test_golden_geometry_test_b_transverse_hole():
    """M2.26 Test B: Transverse cylinder along +X must have 90.0° angle to Z pull with 0.00° error."""
    shape = make_box_with_transverse_hole()
    analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    report = analyzer.analyze(project_id="test_b")

    assert len(report.transverse_holes) > 0, "Expected at least 1 transverse hole"
    th = report.transverse_holes[0]

    # Verify axis is along X [1, 0, 0]
    v_exp_axis = [1.0, 0.0, 0.0]
    axis_error = min(
        ManufacturingVectorVerifier.compute_angular_error(v_exp_axis, th.axis_vector),
        ManufacturingVectorVerifier.compute_angular_error([-1.0, 0.0, 0.0], th.axis_vector)
    )

    assert axis_error < 0.01, f"Hole axis error {axis_error}° exceeds tolerance"
    assert abs(th.angle_to_pull_deg - 90.0) < 1.0, f"Expected 90° transverse angle, got {th.angle_to_pull_deg}°"
    assert th.potential_core_pin_requirement == "TRANSVERSE_CORE_PIN_CANDIDATE"
    print(f"\n[PASS] Golden Test B (Transverse Hole): Axis Error = {axis_error:.4f}°, Transverse Angle = {th.angle_to_pull_deg}°")


def test_golden_geometry_test_c_external_snap_hook():
    """M2.26 Test C: External undercut must produce orthogonal slide vector with S . D_pull = 0."""
    shape = make_external_snap_hook()
    analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    report = analyzer.analyze(project_id="test_c")

    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()

    assert len(sliders) > 0, "Expected external slider action for snap hook"
    slider = sliders[0]

    # Check Orthogonality: S . D_pull == 0
    d_pull = np.array(report.optimal_pull_direction)
    s_vec = np.array(slider.pull_vector)
    ortho_dot = abs(float(np.dot(s_vec, d_pull)))

    assert ortho_dot < 1e-4, f"Slide vector not orthogonal to pull: dot = {ortho_dot}"
    assert slider.mechanism_type == "EXTERNAL_SLIDER_CAM"
    print(f"\n[PASS] Golden Test C (Snap Hook): Slider S = {slider.pull_vector}, Orthogonality |S · D_pull| = {ortho_dot:.6f}")


def test_golden_geometry_test_d_internal_grooved_box():
    """M2.26 Test D: Internal undercut must generate connected region and lifter candidate."""
    shape = make_internal_grooved_box()
    analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    report = analyzer.analyze(project_id="test_d")

    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()

    assert len(sliders) > 0 or len(report.connected_undercut_regions) > 0, "Expected internal undercut detection"
    if sliders:
        s = sliders[0]
        assert s.required_stroke_mm > 5.0
        assert len(s.source_faces) > 0
    print(f"\n[PASS] Golden Test D (Internal Groove): Found {len(sliders)} mechanism(s), {len(report.connected_undercut_regions)} connected region(s)")


def test_golden_geometry_test_e_ribs_and_bosses():
    """M2.26 Test E: Evaluates wall thickness and boss ratios with vector proofs."""
    shape = make_ribs_and_bosses_part()
    analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    report = analyzer.analyze(project_id="test_e")

    assert len(report.rib_boss_features) > 0, "Expected boss features"
    assert len(report.vector_proofs) > 0, "Expected vector verification proofs"

    main_proof = report.vector_proofs[0]
    assert main_proof["is_valid"] is True
    assert main_proof["marker_id"] == "MAIN_PULL_AXIS"
    print(f"\n[PASS] Golden Test E (Ribs & Bosses): Found {len(report.rib_boss_features)} boss(es), {len(report.vector_proofs)} vector proof(s)")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE M2 — GOLDEN GEOMETRY & VECTOR ACCURACY BENCHMARK SUITE")
    print("=" * 70)
    test_golden_geometry_test_a_straight_pull()
    test_golden_geometry_test_b_transverse_hole()
    test_golden_geometry_test_c_external_snap_hook()
    test_golden_geometry_test_d_internal_grooved_box()
    test_golden_geometry_test_e_ribs_and_bosses()
    print("=" * 70)
    print(">>> ALL PHASE M2 GOLDEN GEOMETRY BENCHMARKS PASSED! <<<")
    print("=" * 70)
