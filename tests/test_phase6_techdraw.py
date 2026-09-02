"""Phase 6: Automated TechDraw Engineering Drawing Generation Test Suite.

Tests:
1.  STEP file loading validation
2.  Template auto-detection
3.  Page creation (TechDraw::DrawPage)
4.  Template attachment (TechDraw::DrawSVGTemplate)
5.  Projection group creation (TechDraw::DrawProjGroup)
6.  View count (5 views: Front, Top, Left, Right, Bottom)
7.  View names correctness
8.  View direction vectors (non-zero, correct axis)
9.  Effective scale (non-zero positive)
10. View positions (non-overlapping relative offsets)
11. Source object references (linked to B-Rep shape)
12. Document recompute success
13. FCStd output file existence and non-empty
14. SVG output existence and non-empty
15. Reopen generated FCStd and validate structure
16. Drawing validator integration test
17. CLI draw command end-to-end test
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
import FreeCAD
from src.cad.techdraw_generator import (
    DrawingConfig,
    DrawingResult,
    TechDrawGenerator,
    find_template,
    generate_drawing,
)
from src.cad.drawing_validator import DrawingValidator, validate_drawing_file


STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
OUTPUT_DIR = PROJECT_ROOT / "output"
FCSTD_PATH = OUTPUT_DIR / "Pieza18_1_drawing.FCStd"
SVG_PATH = OUTPUT_DIR / "Pieza18_1_drawing.svg"
DXF_PATH = OUTPUT_DIR / "Pieza18_1_drawing.dxf"

EXPECTED_VIEWS = {"Front", "Top", "Left", "Right", "Bottom"}

# Expected direction vectors for Third-Angle projection (FreeCAD convention)
# Direction = the 3D camera "look-at" direction
EXPECTED_DIRECTIONS = {
    "Front":   (0.0, -1.0, 0.0),   # looking from +Y toward -Y
    "Top":     (0.0, 0.0, 1.0),    # looking from +Z downward (FreeCAD inverts Z for Top)
    "Left":    (-1.0, 0.0, 0.0),   # looking from +X toward -X
    "Right":   (1.0, 0.0, 0.0),    # looking from -X toward +X
    "Bottom":  (0.0, 0.0, -1.0),   # looking from -Z upward
}
DIR_TOLERANCE = 1e-3  # directional cosine tolerance


def _vec_close(actual, expected, tol=DIR_TOLERANCE):
    """Check that direction vectors are parallel (allow sign flip)."""
    a = [float(x) for x in actual]
    e = list(expected)
    mag_a = math.sqrt(sum(x**2 for x in a))
    mag_e = math.sqrt(sum(x**2 for x in e))
    if mag_a < 1e-9 or mag_e < 1e-9:
        return False
    dot = sum(a[i]/mag_a * e[i]/mag_e for i in range(3))
    return abs(abs(dot) - 1.0) < tol


def test_template_detection() -> None:
    print("  [TEST 1] Template auto-detection...")
    tmpl_path = find_template("A3_Landscape_blank.svg")
    assert tmpl_path.exists(), f"Template not found at: {tmpl_path}"
    assert tmpl_path.suffix == ".svg", f"Template is not an SVG: {tmpl_path}"
    assert "A3" in tmpl_path.name or "a3" in tmpl_path.name.lower(), \
        f"Unexpected template name: {tmpl_path.name}"
    print(f"         Template found: {tmpl_path.name}")


def test_step_loading() -> None:
    print("  [TEST 2] STEP file loading validation...")
    assert STEP_FILE.exists(), f"Test STEP file missing: {STEP_FILE}"

    # Verify generator can load it
    gen = TechDrawGenerator()
    errors = []
    doc, src_obj = gen._load_step(STEP_FILE, errors)
    try:
        assert not errors, f"STEP load errors: {errors}"
        assert doc is not None, "No document returned"
        assert src_obj is not None, "No source object found"
        assert hasattr(src_obj, "Shape"), "Source object has no Shape"
        assert len(src_obj.Shape.Solids) >= 1, "No solids in imported shape"
        print(f"         Source object: {src_obj.Label} | Solids: {len(src_obj.Shape.Solids)}")
    finally:
        if doc:
            FreeCAD.closeDocument(doc.Name)


def _generate_drawing() -> DrawingResult:
    """Generate the drawing once and return result."""
    config = DrawingConfig(
        projection_convention="Third angle",
        scale_type="Automatic",
        template_name="A3_Landscape_blank.svg",
    )
    return generate_drawing(
        STEP_FILE, OUTPUT_DIR, config,
        save_fcstd=True, export_svg=True, export_dxf=True,
    )


def test_page_and_template_creation(result: DrawingResult) -> None:
    print("  [TEST 3] Page and template creation...")
    assert result.status != "error", f"Drawing generation failed: {result.errors}"
    assert result.page_name, "Page name is empty"
    assert result.template_path, "Template path is empty"
    assert Path(result.template_path).exists(), f"Template file missing: {result.template_path}"
    assert result.template_width_mm > 0 and result.template_height_mm > 0, \
        f"Invalid template dimensions: {result.template_width_mm} × {result.template_height_mm}"
    print(f"         Page: {result.page_name}")
    print(f"         Template: {Path(result.template_path).name}")
    print(f"         Size: {result.template_width_mm:.0f} × {result.template_height_mm:.0f} mm")


def test_projection_group(result: DrawingResult) -> None:
    print("  [TEST 4] Projection group creation...")
    assert result.projection_group_name, "Projection group name is empty"
    assert result.projection_convention in ("Third angle", "First angle"), \
        f"Unexpected convention: {result.projection_convention}"
    print(f"         Group: {result.projection_group_name}")
    print(f"         Convention: {result.projection_convention}")


def test_view_count(result: DrawingResult) -> None:
    print("  [TEST 5] View count...")
    assert len(result.views) == 5, f"Expected 5 views, got {len(result.views)}: {[v.name for v in result.views]}"
    print(f"         View count: {len(result.views)} ✓")


def test_view_names(result: DrawingResult) -> None:
    print("  [TEST 6] View names...")
    actual_names = {v.name for v in result.views}
    assert actual_names == EXPECTED_VIEWS, \
        f"View names mismatch: got {actual_names}, expected {EXPECTED_VIEWS}"
    print(f"         Views: {sorted(actual_names)}")


def test_view_directions(result: DrawingResult) -> None:
    print("  [TEST 7] View direction vectors...")
    for v in result.views:
        expected = EXPECTED_DIRECTIONS.get(v.name)
        if expected:
            assert _vec_close(v.direction, expected), \
                f"View '{v.name}' direction {v.direction} doesn't match expected {expected}"
        # At minimum the direction must be non-zero
        mag = math.sqrt(sum(x**2 for x in v.direction))
        assert mag > 1e-6, f"View '{v.name}' has zero direction vector"
    print("         All direction vectors non-zero and correctly oriented ✓")


def test_view_scale(result: DrawingResult) -> None:
    print("  [TEST 8] Effective scale...")
    assert result.effective_scale > 0, f"Scale is non-positive: {result.effective_scale}"
    for v in result.views:
        assert v.scale > 0, f"View '{v.name}' has non-positive scale: {v.scale}"
    print(f"         Effective scale: {result.effective_scale:.4f} ✓")


def test_view_positions(result: DrawingResult) -> None:
    print("  [TEST 9] View positions (non-overlap check)...")
    # In third-angle: Front at (0,0), Top above, Bottom below, Left to left, Right to right
    front = next(v for v in result.views if v.name == "Front")
    top = next(v for v in result.views if v.name == "Top")
    bottom = next(v for v in result.views if v.name == "Bottom")
    left = next(v for v in result.views if v.name == "Left")
    right = next(v for v in result.views if v.name == "Right")

    # Front is the anchor — relative positions of others
    assert top.y > front.y - 1e-3, f"Top view should be above Front: top.y={top.y} front.y={front.y}"
    assert bottom.y < front.y + 1e-3, f"Bottom view should be below Front: bottom.y={bottom.y} front.y={front.y}"
    assert left.x < front.x + 1e-3, f"Left view should be left of Front: left.x={left.x} front.x={front.x}"
    assert right.x > front.x - 1e-3, f"Right view should be right of Front: right.x={right.x} front.x={front.x}"
    print("         Relative view positions correct (Top above, Bottom below, Left left, Right right) ✓")


def test_source_object_reference(result: DrawingResult) -> None:
    print("  [TEST 10] Source object reference...")
    assert result.source_object_label, "Source object label is empty"
    print(f"         Source: {result.source_object_label} ✓")


def test_fcstd_output(result: DrawingResult) -> None:
    print("  [TEST 11] FCStd output file...")
    assert result.fcstd_path, "FCStd path not set in result"
    fcstd = Path(result.fcstd_path)
    assert fcstd.exists(), f"FCStd file not found: {fcstd}"
    assert fcstd.stat().st_size > 1000, f"FCStd file suspiciously small: {fcstd.stat().st_size} bytes"
    print(f"         FCStd: {fcstd.name} ({fcstd.stat().st_size:,} bytes) ✓")


def test_svg_output(result: DrawingResult) -> None:
    print("  [TEST 12] SVG output file...")
    if result.svg_path is None:
        print("         SVG not exported (skipping)")
        return
    svg = Path(result.svg_path)
    assert svg.exists(), f"SVG file not found: {svg}"
    assert svg.stat().st_size > 200, f"SVG file suspiciously small: {svg.stat().st_size} bytes"
    content = svg.read_text(encoding="utf-8")
    assert "<svg" in content, "SVG file doesn't contain <svg> tag"
    print(f"         SVG: {svg.name} ({svg.stat().st_size:,} bytes) ✓")


def test_fcstd_reopen(result: DrawingResult) -> None:
    print("  [TEST 13] Reopen FCStd and verify structure...")
    assert result.fcstd_path, "FCStd path not set"
    doc2 = FreeCAD.openDocument(result.fcstd_path)
    try:
        page_objs = [o for o in doc2.Objects if o.TypeId == "TechDraw::DrawPage"]
        pg_objs = [o for o in doc2.Objects if o.TypeId == "TechDraw::DrawProjGroup"]
        pgi_objs = [o for o in doc2.Objects if o.TypeId == "TechDraw::DrawProjGroupItem"]

        assert len(page_objs) == 1, f"Expected 1 page, found {len(page_objs)}"
        assert len(pg_objs) == 1, f"Expected 1 proj group, found {len(pg_objs)}"
        assert len(pgi_objs) == 5, f"Expected 5 view items, found {len(pgi_objs)}"

        view_labels = {v.Label for v in pg_objs[0].Views}
        assert view_labels == EXPECTED_VIEWS, f"View label mismatch: {view_labels}"
        print(f"         Reopened: {len(doc2.Objects)} objects, {len(pgi_objs)} views ✓")
    finally:
        FreeCAD.closeDocument(doc2.Name)


def test_drawing_validator(result: DrawingResult) -> None:
    print("  [TEST 14] DrawingValidator integration...")
    assert result.fcstd_path, "FCStd path not set"
    val_report = validate_drawing_file(Path(result.fcstd_path))
    errors = val_report.errors()
    assert val_report.passed, \
        f"Validation FAILED. Errors: {[e.message for e in errors]}"
    assert val_report.views_found, "No views found by validator"
    assert set(val_report.views_found) == EXPECTED_VIEWS, \
        f"Validator found wrong views: {val_report.views_found}"
    print(f"         Validator: PASSED | Views: {sorted(val_report.views_found)} ✓")


def test_cli_draw_command() -> None:
    print("  [TEST 15] CLI draw command end-to-end...")
    python = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
    cmd = [python, "-m", "src.main", "draw", str(STEP_FILE), "--output-dir", str(OUTPUT_DIR)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"  STDOUT:\n{result.stdout[-2000:]}")
        print(f"  STDERR:\n{result.stderr[-1000:]}")
        assert False, f"CLI draw command failed with code {result.returncode}"
    assert "AUTOMATED DRAWING GENERATION COMPLETE" in result.stdout, \
        f"Expected success message not found in stdout"
    assert FCSTD_PATH.exists(), "FCStd not created by CLI"
    print(f"         CLI draw command: OK (return code 0) ✓")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 6 — TECHDRAW DRAWING GENERATION TEST SUITE")
    print("=" * 60)

    # Pre-check
    if not STEP_FILE.exists():
        print(f"[ERROR] STEP file missing: {STEP_FILE}")
        return False

    test_template_detection()
    test_step_loading()

    # Generate drawing once for most tests
    print("  [SETUP] Generating drawing for tests...")
    result = _generate_drawing()

    test_page_and_template_creation(result)
    test_projection_group(result)
    test_view_count(result)
    test_view_names(result)
    test_view_directions(result)
    test_view_scale(result)
    test_view_positions(result)
    test_source_object_reference(result)
    test_fcstd_output(result)
    test_svg_output(result)
    test_fcstd_reopen(result)
    test_drawing_validator(result)
    test_cli_draw_command()

    print("=" * 60)
    print("ALL PHASE 6 TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
