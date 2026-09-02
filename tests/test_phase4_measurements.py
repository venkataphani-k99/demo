"""Phase 4: Exact CAD Measurement Engine Test Suite.

Validates all deterministic measurement capabilities against input/Pieza18_1.STEP:
1. Cylinder diameter & radius on single faces and multi-face compound features.
2. Cylinder-to-cylinder axis relationships (coaxiality, intersection distance, angular deviation).
3. Planar thickness between parallel faces.
4. Angle measurements between face normals and vector directions.
5. Edge lengths and point-to-point distances.
6. Solid volume, total surface area, and bounding box dimensions.
7. Error handling for invalid entity IDs, non-coaxial cylinder combinations, and non-parallel planar faces.
8. Complete B-Rep entity traceability contract.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.cad.measurements import MeasurementEngine, MeasurementResult
from src.cad.step_loader import load_step


def test_cylinder_diameter_and_radius(engine: MeasurementEngine) -> None:
    """Validate cylinder measurements across single and multi-face features."""
    print("  [TEST] Validating cylinder radius and diameter measurements...")

    # 1. Central Inner Hole (Face4 + Face22)
    m_inner = engine.measure_cylinder_diameter(["Face4", "Face22"])
    assert m_inner.status == "valid"
    assert m_inner.unit == "mm"
    assert m_inner.source_entities == ["Face4", "Face22"]
    assert abs(m_inner.value - 5.50) < 1e-4, f"Expected 5.5 mm, got {m_inner.value}"
    assert abs(m_inner.details["radius"] - 2.75) < 1e-4

    # 2. Central Counterbore (Face5 + Face21)
    m_cbore = engine.measure_cylinder_diameter(["Face5", "Face21"])
    assert m_cbore.status == "valid"
    assert abs(m_cbore.value - 11.00) < 1e-4, f"Expected 11.0 mm, got {m_cbore.value}"
    assert abs(m_cbore.details["radius"] - 5.50) < 1e-4

    # 3. Horizontal Bore (Face6 + Face7 + Face14 + Face15)
    m_bore = engine.measure_cylinder_diameter(["Face6", "Face7", "Face14", "Face15"])
    assert m_bore.status == "valid"
    assert abs(m_bore.value - 10.00) < 1e-4, f"Expected 10.0 mm, got {m_bore.value}"
    assert abs(m_bore.details["radius"] - 5.00) < 1e-4

    # 4. Main Outer Boss (Face8 + Face9)
    m_boss = engine.measure_cylinder_diameter(["Face8", "Face9"])
    assert m_boss.status == "valid"
    assert abs(m_boss.value - 30.00) < 1e-4, f"Expected 30.0 mm, got {m_boss.value}"
    assert abs(m_boss.details["radius"] - 15.00) < 1e-4

    # 5. Side Boss (Face17 + Face18)
    m_side = engine.measure_cylinder_diameter(["Face17", "Face18"])
    assert m_side.status == "valid"
    assert abs(m_side.value - 16.00) < 1e-4, f"Expected 16.0 mm, got {m_side.value}"
    assert abs(m_side.details["radius"] - 8.00) < 1e-4

    # 6. Fillet Radius (Face24)
    m_fillet = engine.measure_cylinder_radius("Face24")
    assert m_fillet.status == "valid"
    assert abs(m_fillet.value - 2.00) < 1e-4, f"Expected 2.0 mm, got {m_fillet.value}"

    print("         Cylinder diameters: 5.5mm, 11.0mm, 10.0mm, 16.0mm, 30.0mm, and 2.0mm fillet verified.")


def test_cylinder_relationships(engine: MeasurementEngine) -> None:
    """Validate spatial and angular relationships between cylinder axes."""
    print("  [TEST] Validating cylinder-to-cylinder relationships...")

    # 1. Coaxiality between Central Inner Hole and Counterbore
    rel_coaxial = engine.measure_cylinder_relationship(["Face4", "Face22"], ["Face5", "Face21"])
    assert rel_coaxial.status == "valid"
    assert rel_coaxial.details["is_coaxial"] is True
    assert abs(rel_coaxial.details["axis_distance"]) < 1e-4
    assert abs(rel_coaxial.details["angle_degrees"]) < 1e-3

    # 2. Perpendicular intersection between Central Hole and Horizontal Bore
    rel_perp = engine.measure_cylinder_relationship(["Face4", "Face22"], ["Face6", "Face7", "Face14", "Face15"])
    assert rel_perp.status == "valid"
    assert rel_perp.details["is_perpendicular"] is True
    assert abs(rel_perp.details["angle_degrees"] - 90.0) < 1e-3
    assert abs(rel_perp.details["axis_distance"]) < 1e-4  # axes intersect at (0, 0, 22)

    print("         Coaxiality (dist=0mm, ang=0°) and perpendicularity (dist=0mm, ang=90°) verified.")


def test_planar_thickness(engine: MeasurementEngine) -> None:
    """Validate thickness / span between parallel planar faces."""
    print("  [TEST] Validating planar thickness measurements...")

    # Distance between parallel vertical end faces Face10 (X=-25) and Face11 (X=+25)
    thick_end = engine.measure_thickness("Face10", "Face11")
    assert thick_end.status == "valid"
    assert abs(thick_end.value - 50.00) < 1e-4, f"Expected 50.0 mm span, got {thick_end.value}"
    assert thick_end.unit == "mm"
    assert thick_end.source_entities == ["Face10", "Face11"]

    print("         Planar end-to-end thickness of 50.0 mm verified.")


def test_angle_measurements(engine: MeasurementEngine) -> None:
    """Validate 3D angular measurements."""
    print("  [TEST] Validating angle measurements...")

    # Angle between Face10 normal (1, 0, 0) and Face16 normal (0, 0, -1) -> 90.0 deg
    ang_plane = engine.measure_angle("Face10", "Face16")
    assert ang_plane.status == "valid"
    assert abs(ang_plane.value - 90.0) < 1e-3

    # Angle between parallel planar normals (Face10 and Face11) -> 0.0 deg
    ang_parallel = engine.measure_angle("Face10", "Face11")
    assert ang_parallel.status == "valid"
    assert abs(ang_parallel.value - 0.0) < 1e-3

    # Angle between arbitrary vectors
    ang_vec = engine.measure_angle([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    assert ang_vec.status == "valid"
    assert abs(ang_vec.value - 90.0) < 1e-3

    print("         Angle measurements (90.0°, 0.0°) verified.")


def test_volume_area_and_bbox(engine: MeasurementEngine) -> None:
    """Validate solid volume, total area, and bounding box."""
    print("  [TEST] Validating global geometry measurements...")

    vol = engine.measure_solid_volume()
    assert vol.status == "valid"
    assert vol.unit == "mm³"
    assert abs(vol.value - 16856.332) < 0.1

    area = engine.measure_total_surface_area()
    assert area.status == "valid"
    assert area.unit == "mm²"
    assert abs(area.value - 6766.739) < 0.1

    bbox = engine.measure_bounding_box()
    assert bbox.status == "valid"
    assert abs(bbox.details["length_x"] - 70.037) < 0.01
    assert abs(bbox.details["length_y"] - 24.014) < 0.01
    assert abs(bbox.details["length_z"] - 30.871) < 0.01

    print("         Volume (16856.332 mm³), Area (6766.739 mm²), BBox (70.037 x 24.014 x 30.871 mm) verified.")


def test_edge_and_point_measurements(engine: MeasurementEngine) -> None:
    """Validate edge length and point distance measurements."""
    print("  [TEST] Validating edge and point-to-point measurements...")

    # Straight long edge (Edge29 has length 46.0 mm)
    e_len = engine.measure_edge_length("Edge29")
    assert e_len.status == "valid"
    assert abs(e_len.value - 46.0) < 1e-3

    # Point to point distance between Vertex1 and Vertex1 is 0.0
    p2p_zero = engine.measure_point_to_point("Vertex1", "Vertex1")
    assert p2p_zero.status == "valid"
    assert abs(p2p_zero.value - 0.0) < 1e-6

    # Symmetry test: dist(p1, p2) == dist(p2, p1)
    p2p_fwd = engine.measure_point_to_point("Vertex1", "Vertex2")
    p2p_rev = engine.measure_point_to_point("Vertex2", "Vertex1")
    assert p2p_fwd.status == "valid"
    assert p2p_rev.status == "valid"
    assert abs(p2p_fwd.value - p2p_rev.value) < 1e-9

    print("         Edge length and point-to-point symmetry verified.")


def test_error_handling(engine: MeasurementEngine) -> None:
    """Validate robustness against invalid or non-coaxial inputs."""
    print("  [TEST] Validating error handling and invalid input rejection...")

    # 1. Non-existent face
    res_missing = engine.measure_cylinder_diameter("Face999")
    assert res_missing.status == "invalid"
    assert "not found" in res_missing.details["error"].lower()

    # 2. Non-cylindrical face for cylinder measurement
    res_noncyl = engine.measure_cylinder_diameter("Face16")  # Face16 is planar
    assert res_noncyl.status == "invalid"
    assert "not a cylindrical surface" in res_noncyl.details["error"].lower()

    # 3. Non-coaxial cylinder combination (Face4 vs Face6 have perpendicular axes)
    res_noncoax = engine.measure_cylinder_diameter(["Face4", "Face6"])
    assert res_noncoax.status == "invalid"
    assert "not coaxial" in res_noncoax.details["error"].lower() or "mismatch" in res_noncoax.details["error"].lower()

    # 4. Non-parallel planar thickness (Face10 vs Face16 are perpendicular)
    res_nonpar = engine.measure_thickness("Face10", "Face16")
    assert res_nonpar.status == "invalid"
    assert "not parallel" in res_nonpar.details["error"].lower()

    print("         All invalid/unsupported conditions rejected cleanly with structured error details.")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 4 — EXACT CAD MEASUREMENT ENGINE TEST SUITE")
    print("=" * 60)

    step_file = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
    if not step_file.exists():
        print(f"[ERROR] STEP file not found: {step_file}", file=sys.stderr)
        return False

    load_res = load_step(step_file)
    try:
        engine = MeasurementEngine(load_res.primary_shape, units="mm")
        test_cylinder_diameter_and_radius(engine)
        test_cylinder_relationships(engine)
        test_planar_thickness(engine)
        test_angle_measurements(engine)
        test_volume_area_and_bbox(engine)
        test_edge_and_point_measurements(engine)
        test_error_handling(engine)
        print("=" * 60)
        print("ALL PHASE 4 TESTS PASSED SUCCESSFULLY.")
        print("=" * 60)
        return True
    finally:
        load_res.close()


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        sys.exit(1)
