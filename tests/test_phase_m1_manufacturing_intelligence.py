"""Phase M1 Benchmark Test Suite & Numerical Validation.

Tests 5 distinct geometric scenarios against the Manufacturing Intelligence Engine:
1. TEST 1: Simple Straight-Pull Housing
2. TEST 2: Housing with External Side Hole
3. TEST 3: Housing with Internal Snap / Undercut
4. TEST 4: Part with Ribs and Bosses
5. TEST 5: Part with Mixed Internal/External Undercuts
"""
import math
import numpy as np
from pathlib import Path

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.cad.mold_analyzer import MoldabilityAnalyzer, ManufacturingReport
from src.cad.slider_locator import SliderLocator, SliderAction
from src.cad.mfg_presets import get_process_preset
from src.cad.mfg_evidence_model import EpistemicState, FindingCategory
from src.cad.ai_manufacturing_reviewer import AIManufacturingReviewer


def create_test_1_straight_pull_box():
    """TEST 1: Clean box housing with flat top and bottom."""
    return Part.makeBox(60, 40, 25)


def create_test_2_box_with_side_hole():
    """TEST 2: Housing with horizontal through-hole along X axis requiring transverse core."""
    box = Part.makeBox(80, 50, 30)
    cyl = Part.makeCylinder(6, 100, FreeCAD.Vector(-10, 25, 15), FreeCAD.Vector(1, 0, 0))
    return box.cut(cyl)


def create_test_3_internal_snap_undercut():
    """TEST 3: Housing with an internal undercut groove on interior sidewall."""
    # Outer box: 70 x 50 x 30
    outer = Part.makeBox(70, 50, 30)
    # Hollow interior cavity
    inner = Part.makeBox(64, 44, 28, FreeCAD.Vector(3, 3, 2))
    pocket = outer.cut(inner)
    # Internal groove undercut in sidewall
    groove = Part.makeBox(30, 3, 6, FreeCAD.Vector(20, 1, 12))
    return pocket.cut(groove)


def create_test_4_ribs_and_bosses():
    """TEST 4: Thin-wall base with a thick boss (ratio > 0.65) and structural ribs."""
    base = Part.makeBox(100, 100, 2.5)  # 2.5mm nominal wall
    boss_outer = Part.makeCylinder(10, 20, FreeCAD.Vector(50, 50, 2.5), FreeCAD.Vector(0, 0, 1))
    boss_inner = Part.makeCylinder(4, 25, FreeCAD.Vector(50, 50, 0), FreeCAD.Vector(0, 0, 1))
    boss = boss_outer.cut(boss_inner)
    rib = Part.makeBox(80, 2.0, 12, FreeCAD.Vector(10, 49, 2.5))
    shape = base.fuse(boss).fuse(rib)
    return shape


def create_test_5_mixed_undercuts():
    """TEST 5: Part with mixed internal/external undercuts and transverse hole."""
    box = Part.makeBox(80, 60, 35)
    # Side hole
    cyl = Part.makeCylinder(5, 100, FreeCAD.Vector(-10, 30, 20), FreeCAD.Vector(1, 0, 0))
    # Side external undercut groove
    groove = Part.makeBox(100, 10, 6, FreeCAD.Vector(-10, -5, 12))
    shape = box.cut(cyl).cut(groove)
    return shape


def run_benchmark_validation():
    print("=" * 70)
    print("PHASE M1 — NUMERICAL VALIDATION & BENCHMARK SUITE")
    print("=" * 70)
    results = []

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: Straight-Pull Housing
    # ─────────────────────────────────────────────────────────────────────────
    t1_shape = create_test_1_straight_pull_box()
    t1_analyzer = MoldabilityAnalyzer(shape=t1_shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    t1_report = t1_analyzer.analyze(project_id="test1_straight")
    t1_locator = SliderLocator(shape=t1_shape, mold_report=t1_report)
    t1_sliders = t1_locator.locate_sliders()

    t1_pass = (
        len(t1_report.pull_direction_candidates) >= 6
        and len(t1_report.undercut_faces) == 0
        and len(t1_sliders) == 0
        and t1_report.moldability_score >= 80.0
    )
    results.append(("TEST 1: Straight-Pull Box", "0 undercuts, 0 sliders", f"{len(t1_report.undercut_faces)} undercuts, {len(t1_sliders)} sliders", 0.0, "PASS" if t1_pass else "FAIL"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: Housing with External Side Hole
    # ─────────────────────────────────────────────────────────────────────────
    t2_shape = create_test_2_box_with_side_hole()
    t2_analyzer = MoldabilityAnalyzer(shape=t2_shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    t2_report = t2_analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test2_side_hole")
    t2_locator = SliderLocator(shape=t2_shape, mold_report=t2_report)
    t2_sliders = t2_locator.locate_sliders()

    t2_pass = (
        len(t2_report.transverse_holes) > 0
        or len(t2_sliders) > 0
        or len(t2_report.undercut_faces) > 0
    )
    results.append(("TEST 2: External Side Hole", "Transverse hole / slider detected", f"{len(t2_report.transverse_holes)} holes, {len(t2_sliders)} sliders", 0.0, "PASS" if t2_pass else "FAIL"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: Internal Snap / Undercut
    # ─────────────────────────────────────────────────────────────────────────
    t3_shape = create_test_3_internal_snap_undercut()
    t3_analyzer = MoldabilityAnalyzer(shape=t3_shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    t3_report = t3_analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test3_internal_snap")
    t3_locator = SliderLocator(shape=t3_shape, mold_report=t3_report)
    t3_sliders = t3_locator.locate_sliders()

    t3_has_internal = any(s.mechanism_type == "INTERNAL_LIFTER_ANGLED" for s in t3_sliders) or len(t3_report.undercut_faces) > 0
    results.append(("TEST 3: Internal Snap", "Internal undercut / lifter flagged", f"{len(t3_sliders)} mechanisms", 0.0, "PASS" if t3_has_internal else "FAIL"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: Part with Ribs and Bosses
    # ─────────────────────────────────────────────────────────────────────────
    t4_shape = create_test_4_ribs_and_bosses()
    t4_analyzer = MoldabilityAnalyzer(shape=t4_shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    t4_report = t4_analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test4_ribs_bosses")

    t4_pass = (
        len(t4_report.rib_boss_features) > 0
        or len(t4_report.wall_thickness_regions) > 0
    )
    results.append(("TEST 4: Ribs & Bosses", "Boss / wall ratios measured", f"{len(t4_report.rib_boss_features)} boss features, {len(t4_report.wall_thickness_regions)} wall regions", 0.0, "PASS" if t4_pass else "FAIL"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: Mixed Internal/External Undercuts & AI Review Layer
    # ─────────────────────────────────────────────────────────────────────────
    t5_shape = create_test_5_mixed_undercuts()
    t5_analyzer = MoldabilityAnalyzer(shape=t5_shape, process_preset_id="GENERAL_PLASTIC_INJECTION")
    t5_report = t5_analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test5_mixed")
    t5_ai_review = AIManufacturingReviewer.generate_review(t5_report)

    t5_pass = (
        len(t5_report.findings) > 0
        and len(t5_ai_review.top_priorities) > 0
        and t5_report.epistemic_summary["KNOWN_FACT"] > 0
    )
    results.append(("TEST 5: Mixed Undercuts & AI", "Structured findings with AI agenda", f"{len(t5_report.findings)} findings, {len(t5_ai_review.top_priorities)} AI priorities", 0.0, "PASS" if t5_pass else "FAIL"))

    # Print Numerical Validation Table
    print(f"{'TEST CASE':<30} | {'EXPECTED':<30} | {'ACTUAL':<35} | {'STATUS'}")
    print("-" * 110)
    for name, exp, act, err, status in results:
        print(f"{name:<30} | {exp:<30} | {act:<35} | {status}")
    print("=" * 110)

    all_passed = all(r[4] == "PASS" for r in results)
    assert all_passed, "One or more Phase M1 validation benchmarks failed!"
    print("\n>>> ALL PHASE M1 NUMERICAL VALIDATION BENCHMARKS PASSED! <<<\n")


if __name__ == "__main__":
    run_benchmark_validation()
