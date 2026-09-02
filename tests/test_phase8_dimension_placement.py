"""Phase 8: TechDraw Dimension View Assignment & Placement Test Suite.

Tests:
1.  D001 view assignment (Ø5.5 on Top view)
2.  D002 view assignment (Ø11.0 on Top view)
3.  D003 view assignment (Ø10.0 on Left/Right view)
4.  D005 view assignment (Ø16.0 on Right/Left view)
5.  D006 view assignment (R2.0 on Top view)
6.  Source geometry traceability (References3D points to valid B-Rep faces)
7.  Dimension value correctness (matches exact 3D geometry measurements)
8.  Projection mapping verification
9.  Placement plan generation (planned, excluded, failed counts)
10. Boundary validation (all placed dimensions within page margin limits)
11. Overlap validation (minimum distance between dimension coordinates)
12. Output FCStd file creation and non-emptiness
13. Drawing reopenability (reopening FCStd confirms DrawViewDimension objects)
14. CLI dimension-drawing command end-to-end
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
import FreeCAD
from src.cad.step_loader import load_step
from src.cad.topology import build_topology_graph
from src.cad.measurements import MeasurementEngine
from src.cad.features import recognize_cad_features
from src.cad.dimensions import DimensionCandidateEngine
from src.cad.view_analysis import analyse_view_visibility
from src.cad.dimension_placement import (
    DimensionPlacementEngine,
    DimensionPlacementPlan,
    export_placement_reports,
    generate_dimensioned_drawing,
    SAFE_SUBSET_TARGETS,
)


STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
DIMENSIONED_FCSTD = OUTPUT_DIR / "Pieza18_1_dimensioned.FCStd"
PLACEMENT_JSON = OUTPUT_DIR / "Pieza18_1_placement.json"
PLACEMENT_TXT = OUTPUT_DIR / "Pieza18_1_placement.txt"


def _build_plan() -> DimensionPlacementPlan:
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    topo = build_topology_graph(shape)
    engine = MeasurementEngine(shape)
    features = recognize_cad_features(shape, topo, engine)
    load_result.close()

    dim_engine = DimensionCandidateEngine(features, engine, topo, STEP_FILE.name)
    cset = dim_engine.generate()
    view_report = analyse_view_visibility(cset)

    placer = DimensionPlacementEngine()
    return placer.create_plan(cset, view_report, str(DIMENSIONED_FCSTD))


def test_d001_view_assignment(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 1] D001 (Ø5.5) view assignment...")
    item = next(i for i in plan.items if i.dimension_id == "D001")
    assert item.selected_view == "Top", f"D001 should be assigned to Top view, got {item.selected_view}"
    assert item.placement_status == "placed", f"D001 placement status: {item.placement_status}"
    assert abs(item.value - 5.5) < 1e-2, f"D001 value mismatch: {item.value}"
    print(f"         D001 assigned to {item.selected_view} view with value {item.formatted_value} ✓")


def test_d002_view_assignment(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 2] D002 (Ø11.0) view assignment...")
    item = next(i for i in plan.items if i.dimension_id == "D002")
    assert item.selected_view == "Top", f"D002 should be assigned to Top view, got {item.selected_view}"
    assert item.placement_status == "placed", f"D002 placement status: {item.placement_status}"
    assert abs(item.value - 11.0) < 1e-2, f"D002 value mismatch: {item.value}"
    print(f"         D002 assigned to {item.selected_view} view with value {item.formatted_value} ✓")


def test_d003_view_assignment(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 3] D003 (Ø10.0) view assignment...")
    item = next(i for i in plan.items if i.dimension_id == "D003")
    assert item.selected_view in ("Left", "Right"), f"D003 should be assigned to Left or Right view, got {item.selected_view}"
    assert item.placement_status == "placed", f"D003 placement status: {item.placement_status}"
    assert abs(item.value - 10.0) < 1e-2, f"D003 value mismatch: {item.value}"
    print(f"         D003 assigned to {item.selected_view} view with value {item.formatted_value} ✓")


def test_d005_view_assignment(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 4] D005 (Ø16.0) view assignment...")
    item = next(i for i in plan.items if i.dimension_id == "D005")
    assert item.selected_view in ("Right", "Left"), f"D005 should be assigned to Right or Left view, got {item.selected_view}"
    assert item.placement_status == "placed", f"D005 placement status: {item.placement_status}"
    assert abs(item.value - 16.0) < 1e-2, f"D005 value mismatch: {item.value}"
    print(f"         D005 assigned to {item.selected_view} view with value {item.formatted_value} ✓")


def test_d006_view_assignment(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 5] D006 (R2.0) view assignment...")
    item = next(i for i in plan.items if i.dimension_id == "D006")
    assert item.selected_view == "Top", f"D006 should be assigned to Top view, got {item.selected_view}"
    assert item.placement_status == "placed", f"D006 placement status: {item.placement_status}"
    assert abs(item.value - 2.0) < 1e-2, f"D006 value mismatch: {item.value}"
    print(f"         D006 assigned to {item.selected_view} view with value {item.formatted_value} ✓")


def test_source_geometry_traceability() -> None:
    print("  [TEST 6] Source geometry traceability...")
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    engine = MeasurementEngine(shape)
    load_result.close()

    for dim_id, info in SAFE_SUBSET_TARGETS.items():
        sub_entity = info["sub_entity"]
        assert sub_entity in engine.face_map, f"Target sub-entity {sub_entity} for {dim_id} not in 3D face map"
        face = engine.face_map[sub_entity]
        assert not face.isNull(), f"Face {sub_entity} is null"
    print(f"         All {len(SAFE_SUBSET_TARGETS)} safe subset targets link to valid 3D B-Rep faces ✓")


def test_dimension_value_correctness() -> None:
    print("  [TEST 7] Dimension value correctness against 3D CAD...")
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    engine = MeasurementEngine(shape)
    load_result.close()

    # D001: Face4 diameter = 5.5
    f4 = engine.face_map["Face4"]
    assert abs(f4.Surface.Radius * 2.0 - 5.5) < 1e-2

    # D002: Face5 diameter = 11.0
    f5 = engine.face_map["Face5"]
    assert abs(f5.Surface.Radius * 2.0 - 11.0) < 1e-2

    # D003: Face6 diameter = 10.0
    f6 = engine.face_map["Face6"]
    assert abs(f6.Surface.Radius * 2.0 - 10.0) < 1e-2

    # D005: Face17 diameter = 16.0
    f17 = engine.face_map["Face17"]
    assert abs(f17.Surface.Radius * 2.0 - 16.0) < 1e-2

    # D006: Face24 radius = 2.0
    f24 = engine.face_map["Face24"]
    assert abs(f24.Surface.Radius - 2.0) < 1e-2

    print("         All dimension values independently verified against OCCT analytic surfaces ✓")


def test_projection_mapping(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 8] Projection mapping quality...")
    for item in plan.items:
        if item.placement_status == "placed":
            assert item.projection_status in ("circular_profile", "edge_on", "planar_profile"), \
                f"Placed dimension {item.dimension_id} has invalid projection status: {item.projection_status}"
    print("         All placed dimensions have confirmed high-quality projection statuses ✓")


def test_placement_plan_structure(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 9] Placement plan structure...")
    assert plan.total_candidates == 20, f"Expected 20 candidates, got {plan.total_candidates}"
    assert plan.placed_count == 5, f"Expected 5 placed dimensions, got {plan.placed_count}"
    assert plan.excluded_count == 15, f"Expected 15 excluded candidates, got {plan.excluded_count}"
    assert plan.failed_count == 0, f"Expected 0 failed placements, got {plan.failed_count}"
    print(f"         Plan structure: {plan.placed_count} placed, {plan.excluded_count} excluded, {plan.failed_count} failed ✓")


def test_boundary_validation(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 10] Page boundary validation...")
    for item in plan.items:
        if item.placement_status == "placed":
            assert 10.0 <= item.x_mm <= 410.0, f"{item.dimension_id} X={item.x_mm} out of page width [10, 410]"
            assert 10.0 <= item.y_mm <= 287.0, f"{item.dimension_id} Y={item.y_mm} out of page height [10, 287]"
    print("         All placed dimensions lie comfortably within printable page limits ✓")


def test_overlap_validation(plan: DimensionPlacementPlan) -> None:
    print("  [TEST 11] Collision & overlap validation...")
    placed = [i for i in plan.items if i.placement_status == "placed"]
    for i, item1 in enumerate(placed):
        for j, item2 in enumerate(placed):
            if i >= j:
                continue
            dist = math.sqrt((item1.x_mm - item2.x_mm) ** 2 + (item1.y_mm - item2.y_mm) ** 2)
            assert dist >= 10.0, f"Collision detected between {item1.dimension_id} and {item2.dimension_id}: dist={dist:.1f}mm"
    print("         Pairwise distance check passed (all annotations separated by >= 10mm) ✓")


def test_fcstd_output() -> None:
    print("  [TEST 12] Dimensioned FCStd file creation...")
    assert DIMENSIONED_FCSTD.exists(), f"Output file missing: {DIMENSIONED_FCSTD}"
    assert DIMENSIONED_FCSTD.stat().st_size > 1000, "FCStd file is suspiciously small"
    print(f"         Dimensioned FCStd exists ({DIMENSIONED_FCSTD.stat().st_size:,} bytes) ✓")


def test_drawing_reopenability() -> None:
    print("  [TEST 13] Reopen dimensioned FCStd and verify dimensions...")
    doc = FreeCAD.openDocument(str(DIMENSIONED_FCSTD))
    try:
        pages = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]
        assert len(pages) == 1, f"Expected 1 page, got {len(pages)}"

        dims = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawViewDimension"]
        assert len(dims) == 5, f"Expected 5 DrawViewDimension objects, found {len(dims)}"

        dim_types = {d.Type for d in dims}
        assert "Diameter" in dim_types, "No Diameter dimensions found in reopened document"
        assert "Radius" in dim_types, "No Radius dimensions found in reopened document"

        for d in dims:
            assert len(d.References3D) >= 1, f"Dimension {d.Name} has empty References3D"
            assert d.MeasureType == "True", f"Dimension {d.Name} MeasureType != 'True'"

        print(f"         Reopened successfully: {len(doc.Objects)} total objects, {len(dims)} DrawViewDimension instances verified ✓")
    finally:
        FreeCAD.closeDocument(doc.Name)


def test_cli_dimension_drawing() -> None:
    print("  [TEST 14] CLI dimension-drawing command end-to-end...")
    python = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
    cmd = [python, "-m", "src.main", "dimension-drawing", str(STEP_FILE), "--output-dir", str(OUTPUT_DIR)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"  STDOUT:\n{result.stdout[-2000:]}")
        print(f"  STDERR:\n{result.stderr[-1000:]}")
    assert result.returncode == 0, f"CLI dimension-drawing failed with code {result.returncode}"
    assert "TECHDRAW DIMENSION PLACEMENT COMPLETE" in result.stdout, "Expected completion message missing"
    assert PLACEMENT_JSON.exists(), "Placement JSON missing"
    assert PLACEMENT_TXT.exists(), "Placement TXT missing"
    print("         CLI dimension-drawing command: OK (code 0) ✓")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 8 — TECHDRAW DIMENSION PLACEMENT TEST SUITE")
    print("=" * 60)

    if not STEP_FILE.exists():
        print(f"[ERROR] STEP file missing: {STEP_FILE}")
        return False

    print("  [SETUP] Generating dimensioned drawing for tests...")
    plan, fcstd_path, json_path, txt_path = generate_dimensioned_drawing(STEP_FILE, OUTPUT_DIR)

    test_d001_view_assignment(plan)
    test_d002_view_assignment(plan)
    test_d003_view_assignment(plan)
    test_d005_view_assignment(plan)
    test_d006_view_assignment(plan)
    test_source_geometry_traceability()
    test_dimension_value_correctness()
    test_projection_mapping(plan)
    test_placement_plan_structure(plan)
    test_boundary_validation(plan)
    test_overlap_validation(plan)
    test_fcstd_output()
    test_drawing_reopenability()
    test_cli_dimension_drawing()

    print("=" * 60)
    print("ALL PHASE 8 TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
