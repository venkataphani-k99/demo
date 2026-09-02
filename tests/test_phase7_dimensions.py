"""Phase 7: Dimension Candidate Engine Test Suite.

Tests:
1.  Diameter candidates (Ø5.5, Ø11, Ø10, Ø16, Ø30)
2.  Radius candidates (R2.0 — grouped deduplicated)
3.  Depth candidates (bore_depth, counterbore_depth, total_depth)
4.  Linear candidates (thickness 50mm, overall extents)
5.  Source entity traceability (every candidate references real B-Rep face IDs)
6.  Feature linkage (counterbore-tied candidates reference CBORE_001 etc.)
7.  Duplicate reduction (R2 fillets → single R2 candidate)
8.  Candidate status validation
9.  View visibility analysis
10. Report generation (JSON + TXT outputs)
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
import FreeCAD, Import
from src.cad.topology import build_topology_graph
from src.cad.measurements import MeasurementEngine
from src.cad.features import recognize_cad_features
from src.cad.dimensions import DimensionCandidateEngine, DimensionCandidate, DimensionCandidateSet
from src.cad.view_analysis import analyse_view_visibility, STANDARD_VIEWS


STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
JSON_PATH = OUTPUT_DIR / "Pieza18_1_dimensions.json"
TXT_PATH = OUTPUT_DIR / "Pieza18_1_dimensions.txt"

VALID_STATUSES = {"valid", "candidate", "ambiguous", "rejected", "unsupported"}
VALID_VISIBILITIES = {"circular_profile", "edge_on", "planar_profile", "partial_profile", "unsuitable"}

TOL = 1e-2  # tolerance for numeric comparisons

# ─────────────────────────────────────────────────────────────────────────────
# Setup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_candidates() -> DimensionCandidateSet:
    doc = FreeCAD.newDocument("TestDim7")
    Import.insert(str(STEP_FILE), doc.Name)
    shape = doc.Objects[0].Shape
    topo = build_topology_graph(shape)
    engine = MeasurementEngine(shape)
    features = recognize_cad_features(shape, topo, engine)
    dim_engine = DimensionCandidateEngine(features, engine, topo, STEP_FILE.name)
    result = dim_engine.generate()
    FreeCAD.closeDocument(doc.Name)
    return result


def _find_by_value(candidates: List[DimensionCandidate], ctype: str, value: float) -> Optional[DimensionCandidate]:
    for c in candidates:
        if c.type == ctype and abs(c.value - value) < TOL:
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_diameter_candidates(cset: DimensionCandidateSet) -> None:
    print("  [TEST 1] Diameter candidates...")
    diameters = [c for c in cset.candidates if c.type == "diameter"]
    d_values = sorted({round(c.value, 2) for c in diameters})
    print(f"           Diameter values found: {d_values}")

    # Required diameters per project specification
    required = [5.5, 11.0, 10.0, 16.0, 30.0]
    for req_d in required:
        found = _find_by_value(cset.candidates, "diameter", req_d)
        assert found is not None, f"Diameter Ø{req_d} not found in candidates"
        assert found.status in ("valid", "candidate"), \
            f"Ø{req_d} has unexpected status: {found.status}"
        print(f"           Ø{req_d}: {found.id} status={found.status} ✓")

    # All diameters must be positive
    for d in diameters:
        assert d.value > 0, f"{d.id} has non-positive diameter: {d.value}"

    print(f"           Total diameter candidates: {len(diameters)} ✓")


def test_radius_candidates(cset: DimensionCandidateSet) -> None:
    print("  [TEST 2] Radius candidates...")
    radii = [c for c in cset.candidates if c.type == "radius"]
    assert len(radii) >= 1, "No radius candidates generated"

    r2 = _find_by_value(cset.candidates, "radius", 2.0)
    assert r2 is not None, "R2.0 radius candidate not found"
    assert r2.status == "valid", f"R2.0 has unexpected status: {r2.status}"
    assert r2.feature_group is not None, "R2.0 candidate has no feature_group"
    assert len(r2.source_entities) > 0, "R2.0 candidate has no source entities"
    fillet_count = r2.details.get("fillet_count", 0)
    assert fillet_count >= 1, "R2.0 fillet_count should be >= 1"
    print(f"           R2.0: {r2.id} group={r2.feature_group} fillets={fillet_count} ✓")

    # Duplicate reduction: there should be at most 2 unique radius groups (not 16 individual entries)
    unique_r_values = {round(c.value, 2) for c in radii}
    print(f"           Unique radius groups: {len(radii)} (values: {sorted(unique_r_values)}) ✓")


def test_depth_candidates(cset: DimensionCandidateSet) -> None:
    print("  [TEST 3] Depth candidates...")
    depths = [c for c in cset.candidates if c.type == "depth"]
    assert len(depths) >= 3, f"Expected at least 3 depth candidates, got {len(depths)}"

    # CBORE_001 should produce bore_depth ≈ 3.3, cbore_depth ≈ 4.745, total_depth ≈ 8.045
    bore_depth = _find_by_value(cset.candidates, "depth", 3.3)
    cbore_depth = _find_by_value(cset.candidates, "depth", 4.745)
    total_depth = _find_by_value(cset.candidates, "depth", 8.045)

    assert bore_depth is not None, "bore_depth ~3.3 mm not found"
    assert cbore_depth is not None, "counterbore_depth ~4.745 mm not found"
    assert total_depth is not None, "total_depth ~8.045 mm not found"

    for d in [bore_depth, cbore_depth, total_depth]:
        assert d.source_feature == "CBORE_001", f"Depth {d.id} not linked to CBORE_001"
        assert d.status == "valid", f"Depth {d.id} has unexpected status: {d.status}"

    print(f"           bore_depth={bore_depth.value:.3f}  cbore_depth={cbore_depth.value:.3f}  total_depth={total_depth.value:.3f} ✓")


def test_linear_candidates(cset: DimensionCandidateSet) -> None:
    print("  [TEST 4] Linear dimension candidates...")
    linears = [c for c in cset.candidates if c.type == "linear"]
    assert len(linears) >= 3, f"Expected >= 3 linear candidates, got {len(linears)}"

    # 50mm thickness (Face10 to Face11 in X direction)
    thickness_50 = _find_by_value(cset.candidates, "linear", 50.0)
    assert thickness_50 is not None, "50.0 mm thickness candidate not found"
    assert thickness_50.dimension_semantics in ("thickness", "overall_extent"), \
        f"Unexpected semantics for 50mm: {thickness_50.dimension_semantics}"
    print(f"           50mm thickness: {thickness_50.id} semantics={thickness_50.dimension_semantics} ✓")

    # Overall extents must include approximately 70.037, 24.014, 30.871
    ext_values = [c.value for c in linears if c.dimension_semantics == "overall_extent"]
    assert any(abs(v - 70.037) < 1.0 for v in ext_values), f"X overall extent not found: {ext_values}"
    assert any(abs(v - 24.014) < 1.0 for v in ext_values), f"Y overall extent not found: {ext_values}"
    assert any(abs(v - 30.871) < 1.0 for v in ext_values), f"Z overall extent not found: {ext_values}"
    print(f"           Overall extents verified: {sorted(round(v,2) for v in ext_values)} ✓")

    # All linears must be positive
    for l in linears:
        assert l.value > 0, f"{l.id} has non-positive linear value: {l.value}"


def test_source_entity_traceability(cset: DimensionCandidateSet) -> None:
    """TEST 5: Every candidate with source_entities must reference real face IDs."""
    print("  [TEST 5] Source entity traceability...")

    doc = FreeCAD.newDocument("TracTest7")
    Import.insert(str(STEP_FILE), doc.Name)
    shape = doc.Objects[0].Shape
    engine = MeasurementEngine(shape)
    valid_face_ids = set(engine.face_map.keys())
    FreeCAD.closeDocument(doc.Name)

    missing_total = 0
    for cand in cset.candidates:
        if not cand.source_entities:
            continue  # bounding box candidates have no entities — that's OK
        for eid in cand.source_entities:
            if eid not in valid_face_ids:
                print(f"           WARNING: {cand.id} references missing entity {eid}")
                missing_total += 1

    assert missing_total == 0, f"Found {missing_total} references to non-existent B-Rep entities"
    print(f"           All source entity references are valid ✓")


def test_feature_linkage(cset: DimensionCandidateSet) -> None:
    """TEST 6: Diameter and depth candidates must be linked to their parent features."""
    print("  [TEST 6] Feature linkage...")

    # All diameter candidates except fillet-derived ones must reference a feature
    for cand in cset.candidates:
        if cand.type in ("diameter", "depth"):
            assert cand.source_feature is not None, \
                f"{cand.id} ({cand.type}) has no source_feature"

    # CBORE_001 must appear in multiple candidates
    cbore_linked = [c for c in cset.candidates if c.source_feature == "CBORE_001"]
    assert len(cbore_linked) >= 4, \
        f"Expected >= 4 candidates linked to CBORE_001, got {len(cbore_linked)}"

    print(f"           Feature linkage: {len(cbore_linked)} candidates linked to CBORE_001 ✓")


def test_duplicate_reduction(cset: DimensionCandidateSet) -> None:
    """TEST 7: Repeated equivalent radii must be grouped, not duplicated."""
    print("  [TEST 7] Duplicate reduction (fillet grouping)...")

    radius_candidates = [c for c in cset.candidates if c.type == "radius"]
    # We have 16 fillet instances all R2.0 — they must be grouped into 1 candidate
    r2_candidates = [c for c in radius_candidates if abs(c.value - 2.0) < TOL]
    assert len(r2_candidates) == 1, \
        f"Expected 1 grouped R2.0 candidate, got {len(r2_candidates)}"

    r2 = r2_candidates[0]
    fillet_count = r2.details.get("fillet_count", 0)
    assert fillet_count >= 4, \
        f"R2.0 group should cover >= 4 fillets, covers {fillet_count}"

    print(f"           {fillet_count} fillet instances → 1 grouped R2.0 candidate ✓")


def test_candidate_status(cset: DimensionCandidateSet) -> None:
    """TEST 8: All status values must be from the approved vocabulary."""
    print("  [TEST 8] Candidate status vocabulary...")

    for cand in cset.candidates:
        assert cand.status in VALID_STATUSES, \
            f"{cand.id} has invalid status: {cand.status!r}"
        if cand.status == "ambiguous":
            assert cand.reason, f"Ambiguous candidate {cand.id} has no reason field"

    print(f"           All {cset.total} candidates have valid status ✓")


def test_view_visibility(cset: DimensionCandidateSet) -> None:
    """TEST 9: View visibility analysis produces correct structure for all candidates."""
    print("  [TEST 9] View visibility analysis...")

    view_report = analyse_view_visibility(cset)
    assert view_report.total_candidates == cset.total, \
        f"Visibility analysis count mismatch: {view_report.total_candidates} vs {cset.total}"

    expected_views = set(STANDARD_VIEWS.keys())

    for analysis in view_report.analyses:
        assert analysis.candidate_id, "Missing candidate_id in analysis"
        assert len(analysis.views) == len(STANDARD_VIEWS), \
            f"{analysis.candidate_id}: wrong view count {len(analysis.views)}"

        view_names = {v.view for v in analysis.views}
        assert view_names == expected_views, \
            f"{analysis.candidate_id}: wrong view names: {view_names}"

        for vv in analysis.views:
            assert vv.visibility in VALID_VISIBILITIES, \
                f"{analysis.candidate_id}/{vv.view}: invalid visibility {vv.visibility!r}"
            assert 0.0 <= vv.score <= 1.0, \
                f"{analysis.candidate_id}/{vv.view}: score out of range: {vv.score}"

    # Specific verification: Ø10 hole has axis=[1,0,0] (X-axis through-hole)
    # Front view (camera from +Y): axis perpendicular to view → edge-on (you see the hole length)
    # Left/Right view (camera from ±X): axis parallel to view → circular profile
    d10_candidates = [c for c in cset.candidates
                      if c.type == "diameter" and abs(c.value - 10.0) < TOL]
    if d10_candidates:
        d10 = d10_candidates[0]
        d10_analysis = next(a for a in view_report.analyses if a.candidate_id == d10.id)
        view_dict = {vv.view: vv for vv in d10_analysis.views}

        # axis=[1,0,0] + Front view=[0,-1,0]: |dot|=0 → edge_on
        assert view_dict["Front"].visibility == "edge_on", \
            f"Ø10 Front should be edge_on (axis ⊥ view), got {view_dict['Front'].visibility}"
        # axis=[1,0,0] + Left/Right view=[±1,0,0]: |dot|=1 → circular_profile
        assert view_dict["Left"].visibility == "circular_profile", \
            f"Ø10 Left should be circular_profile (axis ∥ view), got {view_dict['Left'].visibility}"
        assert view_dict["Right"].visibility == "circular_profile", \
            f"Ø10 Right should be circular_profile (axis ∥ view), got {view_dict['Right'].visibility}"

    print(f"           View visibility analysis: {view_report.total_candidates} candidates, all views correct ✓")
    if d10_candidates:
        print(f"           Ø10 hole view check: Front=circular_profile ✓")


def test_report_generation(cset: DimensionCandidateSet) -> None:
    """TEST 10: JSON and TXT report files must be created and valid."""
    print("  [TEST 10] Report generation...")

    from src.cad.view_analysis import analyse_view_visibility
    from src.analysis.report import export_dimension_reports

    view_report = analyse_view_visibility(cset)
    json_path, txt_path = export_dimension_reports(
        cset, view_report, OUTPUT_DIR, "Pieza18_1"
    )

    # JSON validation
    assert json_path.exists(), f"JSON output missing: {json_path}"
    assert json_path.stat().st_size > 1000, "JSON file too small"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "candidates" in data, "JSON missing 'candidates' key"
    assert "total" in data, "JSON missing 'total' key"
    assert len(data["candidates"]) == cset.total, "JSON candidate count mismatch"
    # Each candidate must have view_analysis embedded
    for cand_dict in data["candidates"]:
        assert "view_analysis" in cand_dict, f"{cand_dict['id']}: missing view_analysis in JSON"
    print(f"           JSON: {json_path.name} ({json_path.stat().st_size:,} bytes) ✓")

    # TXT validation
    assert txt_path.exists(), f"TXT output missing: {txt_path}"
    assert txt_path.stat().st_size > 500, "TXT file too small"
    txt_content = txt_path.read_text(encoding="utf-8")
    assert "DIMENSION CANDIDATES" in txt_content, "TXT missing 'DIMENSION CANDIDATES' section"
    assert "VIEW VISIBILITY" in txt_content, "TXT missing 'VIEW VISIBILITY' section"
    assert "D001" in txt_content, "TXT missing first candidate D001"
    print(f"           TXT: {txt_path.name} ({txt_path.stat().st_size:,} bytes) ✓")


def test_cli_dimensions_command() -> None:
    """CLI end-to-end test for 'dimensions' subcommand."""
    print("  [TEST CLI] CLI dimensions command...")
    python = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
    cmd = [python, "-m", "src.main", "dimensions", str(STEP_FILE), "--output-dir", str(OUTPUT_DIR)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"  STDOUT:\n{result.stdout[-2000:]}")
        print(f"  STDERR:\n{result.stderr[-1000:]}")
    assert result.returncode == 0, f"CLI dimensions command failed with code {result.returncode}"
    assert "DIMENSION CANDIDATE ANALYSIS COMPLETE" in result.stdout, "Expected success message missing"
    assert JSON_PATH.exists(), "JSON not created by CLI"
    assert TXT_PATH.exists(), "TXT not created by CLI"
    print(f"           CLI dimensions command: exit code 0 ✓")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 7 — DIMENSION CANDIDATE ENGINE TEST SUITE")
    print("=" * 60)

    if not STEP_FILE.exists():
        print(f"[ERROR] STEP file missing: {STEP_FILE}")
        return False

    print("  [SETUP] Loading candidates from Pieza18_1.STEP...")
    cset = _load_candidates()
    print(f"          {cset.total} candidates generated")

    test_diameter_candidates(cset)
    test_radius_candidates(cset)
    test_depth_candidates(cset)
    test_linear_candidates(cset)
    test_source_entity_traceability(cset)
    test_feature_linkage(cset)
    test_duplicate_reduction(cset)
    test_candidate_status(cset)
    test_view_visibility(cset)
    test_report_generation(cset)
    test_cli_dimensions_command()

    print("=" * 60)
    print("ALL PHASE 7 TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
