"""Phase 2: STEP Import and Inspection Test Suite.

Validates:
1. Loading real mechanical STEP model (input/Pieza18_1.STEP).
2. Header metadata and unit extraction.
3. B-Rep geometry and topological consistency (solids, shells, faces, edges, vertices).
4. Exact bounding box measurements.
5. Surface and curve type classifications.
6. JSON and text report serialization.
7. Error handling for non-existent files and invalid extensions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.analysis.analyzer import analyze_cad_model
from src.analysis.report import export_analysis_reports
from src.cad.step_loader import (
    CadImportError,
    InvalidExtensionError,
    load_step,
    parse_step_header,
)


def test_step_header_parsing(step_path: Path) -> None:
    """Validate STEP header parsing directly from raw file."""
    print("  [TEST] Parsing STEP header metadata...")
    meta = parse_step_header(step_path)
    assert "AP214" in meta.schema or "AUTOMOTIVE_DESIGN" in meta.schema, f"Unexpected schema: {meta.schema}"
    assert meta.units == "mm", f"Expected 'mm', got: {meta.units}"
    assert "SolidWorks" in meta.originating_system, f"Expected SolidWorks in originating system, got: {meta.originating_system}"
    print(f"         Schema: {meta.schema}, Units: {meta.units}, System: {meta.originating_system}")


def test_step_loading_and_analysis(step_path: Path, output_dir: Path) -> None:
    """Validate B-Rep geometry, topology, and report generation on real STEP file."""
    print("  [TEST] Loading STEP file via FreeCAD...")
    result = load_step(step_path)
    try:
        assert result.is_valid is True
        assert len(result.objects) >= 1
        assert result.primary_shape is not None
        assert not result.primary_shape.isNull()

        # Run analysis
        print("  [TEST] Inspecting B-Rep topology and geometry...")
        analysis = analyze_cad_model(result)

        # 1. Topology assertions
        topo = analysis.topology
        print(f"         Solids: {topo.solids}, Faces: {topo.faces}, Edges: {topo.edges}, Vertices: {topo.vertices}")
        assert topo.solids == 1, f"Expected 1 solid, got {topo.solids}"
        assert topo.shells == 1, f"Expected 1 shell, got {topo.shells}"
        assert topo.faces == 43, f"Expected 43 faces, got {topo.faces}"
        assert topo.edges == 103, f"Expected 103 edges, got {topo.edges}"
        assert topo.vertices == 62, f"Expected 62 vertices, got {topo.vertices}"

        # 2. Bounding box assertions
        bbox = analysis.bounding_box
        print(f"         Dimensions: {bbox.length_x:.3f} x {bbox.length_y:.3f} x {bbox.length_z:.3f} mm")
        assert abs(bbox.length_x - 70.037) < 0.01, f"Unexpected length_x: {bbox.length_x}"
        assert abs(bbox.length_y - 24.014) < 0.01, f"Unexpected length_y: {bbox.length_y}"
        assert abs(bbox.length_z - 30.871) < 0.01, f"Unexpected length_z: {bbox.length_z}"

        # 3. Surface classification assertions
        surfs = analysis.surface_classification
        print(f"         Surface breakdown: {surfs}")
        assert surfs.get("Plane", 0) == 8, f"Expected 8 planar faces, got {surfs.get('Plane', 0)}"
        assert surfs.get("Cylinder", 0) == 22, f"Expected 22 cylindrical faces, got {surfs.get('Cylinder', 0)}"
        assert surfs.get("Toroid", 0) == 6, f"Expected 6 toroidal faces, got {surfs.get('Toroid', 0)}"
        assert surfs.get("BSplineSurface", 0) == 7, f"Expected 7 b-spline surfaces, got {surfs.get('BSplineSurface', 0)}"

        # 4. Curve classification assertions
        curves = analysis.curve_classification
        print(f"         Curve breakdown: {curves}")
        assert curves.get("Line", 0) == 38, f"Expected 38 line edges, got {curves.get('Line', 0)}"
        assert curves.get("Circle", 0) == 41, f"Expected 41 circular edges, got {curves.get('Circle', 0)}"
        assert curves.get("BSplineCurve", 0) == 24, f"Expected 24 b-spline curves, got {curves.get('BSplineCurve', 0)}"

        # 5. Report generation assertions
        print("  [TEST] Generating and validating output reports...")
        json_path, txt_path, *_ = export_analysis_reports(analysis, output_dir)
        assert json_path.exists(), f"JSON report not created at: {json_path}"
        assert txt_path.exists(), f"Text report not created at: {txt_path}"
        assert json_path.stat().st_size > 0, "JSON report is empty"
        assert txt_path.stat().st_size > 0, "Text report is empty"

        # Validate JSON content
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["filename"] == step_path.name
            assert data["topology"]["faces"] == 43
            total_faces = (
                len(data.get("cylindrical_faces", []))
                + len(data.get("planar_faces", []))
                + len(data.get("toroidal_faces", []))
                + len(data.get("bspline_faces", []))
            )
            assert total_faces == 43, f"Expected 43 total categorized faces, got {total_faces}"
            assert len(data["edges"]) == 103
            assert len(data["vertices"]) == 62

        print(f"         JSON Report validated: {json_path.name} ({json_path.stat().st_size:,} bytes)")
        print(f"         Text Report validated: {txt_path.name} ({txt_path.stat().st_size:,} bytes)")

    finally:
        result.close()


def test_error_handling() -> None:
    """Validate error handling for invalid inputs."""
    print("  [TEST] Validating error handling for invalid inputs...")

    # Non-existent file
    try:
        load_step(PROJECT_ROOT / "input" / "non_existent_file.step")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        print("         Caught expected FileNotFoundError.")

    # Invalid extension
    try:
        load_step(PROJECT_ROOT / "requirements.txt")
        assert False, "Expected InvalidExtensionError"
    except InvalidExtensionError:
        print("         Caught expected InvalidExtensionError.")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 2 — STEP IMPORT & INSPECTION TEST SUITE")
    print("=" * 60)

    step_file = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
    output_dir = PROJECT_ROOT / "output"

    if not step_file.exists():
        print(f"[ERROR] STEP test file not found at: {step_file}", file=sys.stderr)
        return False

    try:
        test_step_header_parsing(step_file)
        test_step_loading_and_analysis(step_file, output_dir)
        test_error_handling()
        print("=" * 60)
        print("ALL PHASE 2 TESTS PASSED SUCCESSFULLY.")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n[TEST FAILED] {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        sys.exit(1)
