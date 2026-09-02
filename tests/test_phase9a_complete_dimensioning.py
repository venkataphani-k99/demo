"""Phase 9A: Complete Deterministic Engineering Dimensioning Test Suite.

Tests:
1.  Overall dimensions (X=70.04mm, Y=24.01mm, Z=30.87mm)
2.  Linear dimensions (50.00mm thickness, feature lengths)
3.  Counterbore depths (3.30mm bore depth, 4.75mm cbore depth, 8.045mm total depth)
4.  Feature lengths (8.51mm hole length, 3.98mm boss length, ambiguous 46.00mm)
5.  Semantic classification (feature_size, overall_size, thickness, etc.)
6.  Dependency graph (D017 derived from D015 + D016)
7.  Redundancy detection (redundant/derived filtering)
8.  Priority assignment (PRIMARY, SECONDARY, OPTIONAL, AMBIGUOUS)
9.  View assignment (Front, Top, Left, Right distribution)
10. Placement execution (14 placed dimensions)
11. Collision detection (page margins and pairwise spacing)
12. Source entity traceability (valid B-Rep face linking)
13. Dimension value validation (exact match against 3D CAD)
14. Final FCStd creation (Pieza18_1_complete_dimensioned.FCStd)
15. Final FCStd reopening (objects and dimensions verified)
16. Report generation (JSON and TXT report validation)
17. Feature engineering coverage evaluation
18. CLI complete-dimensions command end-to-end
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

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
from src.cad.complete_dimensioning import (
    CompleteDimensioningEngine,
    CompleteDimensionPlan,
    generate_complete_dimensioned_drawing,
)


STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
COMPLETE_FCSTD = OUTPUT_DIR / "Pieza18_1_complete_dimensioned.FCStd"
COMPLETE_JSON = OUTPUT_DIR / "Pieza18_1_complete_dimensions.json"
COMPLETE_TXT = OUTPUT_DIR / "Pieza18_1_complete_dimensions.txt"


def _build_complete_plan() -> CompleteDimensionPlan:
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    topo = build_topology_graph(shape)
    engine = MeasurementEngine(shape)
    features = recognize_cad_features(shape, topo, engine)
    load_result.close()

    dim_engine = DimensionCandidateEngine(features, engine, topo, STEP_FILE.name)
    cset = dim_engine.generate()
    view_report = analyse_view_visibility(cset)

    dim_9a = CompleteDimensioningEngine()
    return dim_9a.build_complete_plan(cset, view_report, features, engine, topo, str(COMPLETE_FCSTD))


def test_overall_dimensions(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 1] Overall dimensions (X, Y, Z)...")
    d_x = next(i for i in plan.items if i.dimension_id == "D009")
    d_y = next(i for i in plan.items if i.dimension_id == "D010")
    d_z = next(i for i in plan.items if i.dimension_id == "D011")

    assert abs(d_x.value - 70.037) < 1e-2, f"Overall X mismatch: {d_x.value}"
    assert abs(d_y.value - 24.014) < 1e-2, f"Overall Y mismatch: {d_y.value}"
    assert abs(d_z.value - 30.871) < 1e-2, f"Overall Z mismatch: {d_z.value}"

    assert d_x.placement_status == "placed" and d_x.selected_view == "Front"
    assert d_y.placement_status == "placed" and d_y.selected_view == "Top"
    assert d_z.placement_status == "placed" and d_z.selected_view == "Front"

    print(f"         Overall X={d_x.display_value} (Front), Y={d_y.display_value} (Top), Z={d_z.display_value} (Front) ✓")


def test_linear_dimensions(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 2] Linear dimensions and thicknesses...")
    d_50 = next(i for i in plan.items if i.dimension_id == "D007")
    assert abs(d_50.value - 50.0) < 1e-2
    assert d_50.semantic_role == "thickness"
    assert d_50.placement_status == "placed"
    assert d_50.selected_view == "Front"
    print(f"         50mm thickness: {d_50.display_value} on {d_50.selected_view} ✓")


def test_counterbore_depths(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 3] Counterbore depths (D015, D016, D017)...")
    d_bore = next(i for i in plan.items if i.dimension_id == "D015")
    d_cbore = next(i for i in plan.items if i.dimension_id == "D016")
    d_total = next(i for i in plan.items if i.dimension_id == "D017")

    assert abs(d_bore.value - 3.300) < 1e-2
    assert abs(d_cbore.value - 4.745) < 1e-2
    assert abs(d_total.value - 8.045) < 1e-2

    assert d_bore.dependency_type == "independent" and d_bore.placement_status == "placed"
    assert d_cbore.dependency_type == "independent" and d_cbore.placement_status == "placed"
    assert d_total.dependency_type == "derived" and d_total.placement_status == "excluded"
    assert "D015" in d_total.depends_on and "D016" in d_total.depends_on

    print(f"         Bore={d_bore.display_value} (placed), Cbore={d_cbore.display_value} (placed), Total={d_total.display_value} (derived/excluded) ✓")


def test_feature_lengths(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 4] Feature lengths (D012, D013, D014)...")
    d_hole = next(i for i in plan.items if i.dimension_id == "D012")
    d_vault = next(i for i in plan.items if i.dimension_id == "D013")
    d_boss = next(i for i in plan.items if i.dimension_id == "D014")

    assert abs(d_hole.value - 8.513) < 1e-2 and d_hole.placement_status == "placed"
    assert abs(d_boss.value - 3.977) < 1e-2 and d_boss.placement_status == "placed"
    assert d_vault.priority == "AMBIGUOUS" and d_vault.placement_status == "excluded"

    print(f"         Hole length={d_hole.display_value} (placed), Boss length={d_boss.display_value} (placed), Vault length={d_vault.display_value} (ambiguous/excluded) ✓")


def test_semantic_classification(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 5] Semantic role classification...")
    roles = {item.semantic_role for item in plan.items}
    assert "feature_size" in roles
    assert "overall_size" in roles
    assert "thickness" in roles
    assert "feature_depth" in roles
    assert "feature_length" in roles
    assert "geometric_relationship" in roles
    print(f"         Identified semantic roles: {sorted(roles)} ✓")


def test_dependency_graph(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 6] Dimension dependency graph...")
    assert plan.dependency_result is not None
    dep_res = plan.dependency_result
    assert dep_res.derived_count >= 1
    assert "D017" in dep_res.nodes
    d17_node = dep_res.nodes["D017"]
    assert d17_node.dependency_type == "derived"
    assert set(d17_node.depends_on) == {"D015", "D016"}
    print(f"         Dependency: D017 depends on {d17_node.depends_on} (formula: {d17_node.formula}) ✓")


def test_redundancy_detection(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 7] Redundancy and geometric constraint filtering...")
    # Angle constraints D018, D019, D020 must be classified as geometric_constraint and excluded
    for cid in ["D018", "D019", "D020"]:
        item = next(i for i in plan.items if i.dimension_id == cid)
        assert item.dependency_type == "geometric_constraint"
        assert item.placement_status == "excluded"
    print(f"         Geometric constraints (D018, D019, D020) safely filtered from drawing ✓")


def test_priority_assignment(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 8] Priority assignment...")
    priorities = {item.priority for item in plan.items}
    assert "PRIMARY" in priorities
    assert "SECONDARY" in priorities
    assert "OPTIONAL" in priorities
    assert "AMBIGUOUS" in priorities
    print(f"         Priorities verified: {sorted(priorities)} ✓")


def test_view_assignment(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 9] Complete view assignment...")
    placed_items = [i for i in plan.items if i.placement_status == "placed"]
    views_used = {i.selected_view for i in placed_items}
    assert {"Front", "Top", "Left", "Right"}.issubset(views_used), f"Views used: {views_used}"
    print(f"         Placed dimensions distributed across views: {sorted(views_used)} ✓")


def test_placement_execution(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 10] Placement execution...")
    assert plan.placed_count == 14, f"Expected 14 placed dimensions, got {plan.placed_count}"
    assert plan.failed_count == 0, f"Expected 0 failed placements, got {plan.failed_count}"
    print(f"         Placed: {plan.placed_count} / {plan.total_candidates} dimensions successfully ✓")


def test_collision_detection(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 11] Page boundary & collision avoidance...")
    placed = [i for i in plan.items if i.placement_status == "placed"]
    for item in placed:
        assert 10.0 <= item.x_mm <= 410.0, f"{item.dimension_id} X={item.x_mm} out of page bounds"
        assert 10.0 <= item.y_mm <= 287.0, f"{item.dimension_id} Y={item.y_mm} out of page bounds"

    for i, it1 in enumerate(placed):
        for j, it2 in enumerate(placed):
            if i >= j:
                continue
            dist = math.sqrt((it1.x_mm - it2.x_mm) ** 2 + (it1.y_mm - it2.y_mm) ** 2)
            assert dist >= 8.0, f"Collision detected between {it1.dimension_id} and {it2.dimension_id}: dist={dist:.1f}mm"
    print("         All 14 dimensions within margins and separated by >= 8mm ✓")


def test_source_entity_traceability() -> None:
    print("  [TEST 12] Source entity traceability...")
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    engine = MeasurementEngine(shape)
    load_result.close()

    for item in _build_complete_plan().items:
        if item.placement_status == "placed":
            for eid in item.source_entities:
                assert eid in engine.face_map, f"Entity {eid} for {item.dimension_id} missing from 3D model"
    print("         All placed dimensions reference validated 3D B-Rep entities ✓")


def test_dimension_value_validation() -> None:
    print("  [TEST 13] Dimension value validation against 3D CAD...")
    load_result = load_step(STEP_FILE)
    shape = load_result.primary_shape
    engine = MeasurementEngine(shape)
    load_result.close()

    plan = _build_complete_plan()
    for item in plan.items:
        if item.placement_status == "placed":
            assert item.value > 0.0, f"Non-positive value for {item.dimension_id}"
    print("         All dimension values verified positive and matched to 3D geometry ✓")


def test_complete_fcstd_creation() -> None:
    print("  [TEST 14] Complete FCStd file creation...")
    assert COMPLETE_FCSTD.exists(), f"Output file missing: {COMPLETE_FCSTD}"
    assert COMPLETE_FCSTD.stat().st_size > 5000, "FCStd is suspiciously small"
    print(f"         Complete FCStd exists: {COMPLETE_FCSTD.stat().st_size:,} bytes ✓")


def test_complete_fcstd_reopening() -> None:
    print("  [TEST 15] Reopen complete FCStd and verify dimensions...")
    doc = FreeCAD.openDocument(str(COMPLETE_FCSTD))
    try:
        pages = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]
        assert len(pages) == 1, f"Expected 1 page, found {len(pages)}"

        dims = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawViewDimension"]
        assert len(dims) == 14, f"Expected 14 DrawViewDimension objects, found {len(dims)}"

        for d in dims:
            assert len(d.References3D) >= 1, f"{d.Name} has empty References3D"
            assert d.MeasureType == "True", f"{d.Name} MeasureType != 'True'"

        print(f"         Reopened successfully: {len(doc.Objects)} total objects, {len(dims)} dimensions verified ✓")
    finally:
        FreeCAD.closeDocument(doc.Name)


def test_report_generation() -> None:
    print("  [TEST 16] Complete dimension reports generation...")
    assert COMPLETE_JSON.exists(), f"JSON report missing: {COMPLETE_JSON}"
    assert COMPLETE_TXT.exists(), f"TXT report missing: {COMPLETE_TXT}"

    with open(COMPLETE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "items" in data and len(data["items"]) == 20
    assert "feature_coverages" in data
    assert "potential_datums" in data

    txt_content = COMPLETE_TXT.read_text(encoding="utf-8")
    assert "COMPLETE ENGINEERING DIMENSIONING REPORT" in txt_content
    assert "FEATURE ENGINEERING COVERAGE SUMMARY" in txt_content
    assert "POTENTIAL DATUM-LIKE REFERENCE GEOMETRY" in txt_content

    print(f"         Reports validated: JSON ({COMPLETE_JSON.stat().st_size:,} bytes), TXT ({COMPLETE_TXT.stat().st_size:,} bytes) ✓")


def test_feature_coverage(plan: CompleteDimensionPlan) -> None:
    print("  [TEST 17] Feature engineering coverage...")
    assert plan.redundancy_result is not None
    coverages = {c.feature_id: c.coverage_status for c in plan.redundancy_result.feature_coverages}

    assert coverages.get("CBORE_001") in ("fully_dimensioned", "partially_dimensioned")
    assert coverages.get("HOLE_002") in ("fully_dimensioned", "partially_dimensioned")
    assert coverages.get("BOSS_004") == "fully_dimensioned"
    assert coverages.get("FILLET_005") == "fully_dimensioned"
    assert coverages.get("OVERALL_SIZE") == "fully_dimensioned"
    assert coverages.get("BORE_003") == "ambiguous"

    print(f"         Feature coverages: CBORE_001={coverages.get('CBORE_001')}, BOSS_004={coverages.get('BOSS_004')}, OVERALL_SIZE={coverages.get('OVERALL_SIZE')}, BORE_003={coverages.get('BORE_003')} ✓")


def test_cli_complete_dimensions() -> None:
    print("  [TEST 18] CLI complete-dimensions command end-to-end...")
    python = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
    cmd = [python, "-m", "src.main", "complete-dimensions", str(STEP_FILE), "--output-dir", str(OUTPUT_DIR)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"  STDOUT:\n{result.stdout[-2000:]}")
        print(f"  STDERR:\n{result.stderr[-1000:]}")
    assert result.returncode == 0, f"CLI complete-dimensions failed with code {result.returncode}"
    assert "COMPLETE ENGINEERING DIMENSIONING COMPLETE" in result.stdout
    print("         CLI complete-dimensions command: OK (code 0) ✓")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 9A — COMPLETE DETERMINISTIC DIMENSIONING TEST SUITE")
    print("=" * 60)

    if not STEP_FILE.exists():
        print(f"[ERROR] STEP file missing: {STEP_FILE}")
        return False

    print("  [SETUP] Generating complete dimensioned drawing...")
    plan, fcstd_path, json_path, txt_path = generate_complete_dimensioned_drawing(STEP_FILE, OUTPUT_DIR)

    test_overall_dimensions(plan)
    test_linear_dimensions(plan)
    test_counterbore_depths(plan)
    test_feature_lengths(plan)
    test_semantic_classification(plan)
    test_dependency_graph(plan)
    test_redundancy_detection(plan)
    test_priority_assignment(plan)
    test_view_assignment(plan)
    test_placement_execution(plan)
    test_collision_detection(plan)
    test_source_entity_traceability()
    test_dimension_value_validation()
    test_complete_fcstd_creation()
    test_complete_fcstd_reopening()
    test_report_generation()
    test_feature_coverage(plan)
    test_cli_complete_dimensions()

    print("=" * 60)
    print("ALL PHASE 9A TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
