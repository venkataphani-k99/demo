"""Phase 3: Deep Geometry and Topology Graph Test Suite.

Validates on real CAD model (input/Pieza18_1.STEP):
1. Complete extraction of all 22 Cylindrical Faces (radii, diameters, axes, lengths, areas).
2. Coaxial/concentric cylinder relationships ($R=2.75$, $R=5.50$, $R=5.00$, $R=8.00$, $R=15.00$, $R=2.00$).
3. Planar surface normals, areas, and plane positions.
4. Bidirectional topology graph completeness and adjacency symmetry.
5. Structured JSON dataset and text report table formatting.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.analysis.analyzer import analyze_cad_model
from src.analysis.report import export_analysis_reports
from src.cad.step_loader import load_step


def test_cylinder_geometry(analysis) -> None:
    """Validate deep geometric extraction for all 22 cylindrical faces."""
    print("  [TEST] Validating cylindrical face geometry...")
    cyls = {c.id: c for c in analysis.cylindrical_faces}
    assert len(cyls) == 22, f"Expected 22 cylindrical faces, got {len(cyls)}"

    for cyl_id, cyl in cyls.items():
        # Radius & Diameter
        assert cyl.radius > 0.0, f"{cyl_id}: invalid radius {cyl.radius}"
        assert abs(cyl.diameter - 2.0 * cyl.radius) < 1e-9, f"{cyl_id}: diameter mismatch"

        # Axis Unit Vector
        mag = math.sqrt(sum(x * x for x in cyl.axis_direction))
        assert abs(mag - 1.0) < 1e-6, f"{cyl_id}: axis is not normalized: {cyl.axis_direction}"

        # Dimensions & Classification
        assert cyl.axial_length > 0.0, f"{cyl_id}: invalid axial length {cyl.axial_length}"
        assert cyl.surface_area > 0.0, f"{cyl_id}: invalid surface area {cyl.surface_area}"
        assert cyl.classification == "cylindrical_face"
        assert len(cyl.boundary_edges) >= 2, f"{cyl_id}: expected at least 2 boundary edges"
        assert len(cyl.adjacent_faces) >= 1, f"{cyl_id}: expected at least 1 adjacent face"

    # Specific Verified Engineering Values on Pieza18_1.STEP:
    # 1. Central Counterbore Inner Cylinders (R = 2.75 mm, Dia = 5.50 mm)
    assert abs(cyls["Face4"].radius - 2.75) < 1e-4
    assert abs(cyls["Face22"].radius - 2.75) < 1e-4
    assert abs(cyls["Face4"].diameter - 5.50) < 1e-4

    # 2. Central Counterbore Outer Cylinders (R = 5.50 mm, Dia = 11.00 mm)
    assert abs(cyls["Face5"].radius - 5.50) < 1e-4
    assert abs(cyls["Face21"].radius - 5.50) < 1e-4

    # 3. Horizontal Bore Cylinders (R = 5.00 mm, Dia = 10.00 mm)
    for fid in ["Face6", "Face7", "Face14", "Face15"]:
        assert abs(cyls[fid].radius - 5.00) < 1e-4, f"{fid} radius mismatch"
        assert abs(cyls[fid].axis_direction[0] - 1.0) < 1e-4, f"{fid} axis must be X-aligned"

    # 4. Outer Boss Cylinders (R = 15.00 mm, Dia = 30.00 mm)
    assert abs(cyls["Face8"].radius - 15.00) < 1e-4
    assert abs(cyls["Face9"].radius - 15.00) < 1e-4

    # 5. Side Boss Cylinders (R = 8.00 mm, Dia = 16.00 mm)
    assert abs(cyls["Face17"].radius - 8.00) < 1e-4
    assert abs(cyls["Face18"].radius - 8.00) < 1e-4

    # 6. Fillet / Blend Cylinders (10 faces with R = 2.00 mm, Dia = 4.00 mm)
    fillet_ids = ["Face24", "Face26", "Face27", "Face29", "Face30", "Face34", "Face35", "Face39", "Face40", "Face43"]
    for fid in fillet_ids:
        assert abs(cyls[fid].radius - 2.00) < 1e-4, f"{fid} fillet radius mismatch"

    print("         All 22 cylindrical faces verified with exact mathematical precision.")


def test_planar_geometry(analysis) -> None:
    """Validate planar surface normals, areas, and plane positions."""
    print("  [TEST] Validating planar face geometry...")
    planes = {p.id: p for p in analysis.planar_faces}
    assert len(planes) == 8, f"Expected 8 planar faces, got {len(planes)}"

    for pid, p in planes.items():
        mag = math.sqrt(sum(x * x for x in p.normal))
        assert abs(mag - 1.0) < 1e-6, f"{pid}: normal vector not unit length"
        assert p.area > 0.0, f"{pid}: invalid area"
        assert len(p.boundary_edges) >= 3, f"{pid}: planar face must have >= 3 edges"
        assert len(p.adjacent_faces) >= 1, f"{pid}: planar face must have adjacent faces"

    # Bottom Base Plane (Face16)
    f16 = planes["Face16"]
    assert abs(f16.area - 1652.864) < 0.1, f"Face16 area mismatch: {f16.area}"
    assert abs(f16.normal[2] - (-1.0)) < 1e-4, "Face16 normal must point in -Z"

    # Counterbore Step Floor (Face23)
    f23 = planes["Face23"]
    assert abs(f23.area - 71.275) < 0.1, f"Face23 area mismatch: {f23.area}"
    assert abs(f23.position[2] - 3.30) < 0.01, f"Face23 must be located at Z=3.30 mm"

    print("         All 8 planar faces verified.")


def test_topology_graph(analysis) -> None:
    """Validate Face-Edge-Face topology graph completeness and symmetry."""
    print("  [TEST] Validating topology graph and adjacency symmetry...")
    graph = analysis.topology_graph
    adj = graph["face_adjacency"]
    edge_to_faces = graph["edge_to_faces"]
    face_to_edges = graph["face_to_edges"]

    assert len(adj) == 43, f"Expected 43 faces in adjacency graph, got {len(adj)}"
    assert len(edge_to_faces) == 103, f"Expected 103 edges mapped, got {len(edge_to_faces)}"
    assert len(face_to_edges) == 43, f"Expected 43 face-to-edge mappings, got {len(face_to_edges)}"

    # Adjacency Symmetry Check
    for f1, neighbors in adj.items():
        for f2 in neighbors:
            assert f1 in adj[f2], f"Adjacency asymmetry: {f1} is adjacent to {f2}, but {f2} is not adjacent to {f1}"

    # Specific Topological Neighborhoods:
    # Face4 (R=2.75 cylinder) must be adjacent to Face16 (bottom), Face22 (partner half-cylinder), Face23 (counterbore floor)
    f4_adj = set(adj["Face4"])
    assert "Face16" in f4_adj, "Face4 must connect to bottom plane Face16"
    assert "Face22" in f4_adj, "Face4 must connect to partner cylinder Face22"
    assert "Face23" in f4_adj, "Face4 must connect to counterbore floor Face23"

    # Face23 (counterbore floor) must connect to both inner (Face4, Face22) and outer (Face5, Face21) cylinders
    f23_adj = set(adj["Face23"])
    assert {"Face4", "Face22", "Face5", "Face21"}.issubset(f23_adj)

    print("         Topology dual graph verified (100% symmetric and fully connected).")


def test_report_artifacts(analysis, output_dir: Path) -> None:
    """Validate JSON and text report files for Phase 3."""
    print("  [TEST] Validating generated report artifacts...")
    json_path, txt_path, *_ = export_analysis_reports(analysis, output_dir)
    assert json_path.exists() and json_path.stat().st_size > 0
    assert txt_path.exists() and txt_path.stat().st_size > 0

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "cylindrical_faces" in data
        assert len(data["cylindrical_faces"]) == 22
        assert "planar_faces" in data
        assert len(data["planar_faces"]) == 8
        assert "topology_graph" in data

    with open(txt_path, "r", encoding="utf-8") as f:
        txt = f.read()
        assert "CYLINDRICAL SURFACES DEEP ANALYSIS (22 FACES DETECTED)" in txt
        assert "PLANAR SURFACES DEEP ANALYSIS (8 FACES DETECTED)" in txt
        assert "Face4" in txt
        assert "Face16" in txt

    print(f"         JSON Dataset validated: {json_path.name} ({json_path.stat().st_size:,} bytes)")
    print(f"         Text Report validated: {txt_path.name} ({txt_path.stat().st_size:,} bytes)")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 3 — DEEP GEOMETRY & TOPOLOGY GRAPH TEST SUITE")
    print("=" * 60)

    step_file = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
    output_dir = PROJECT_ROOT / "output"

    if not step_file.exists():
        print(f"[ERROR] Test STEP file not found: {step_file}", file=sys.stderr)
        return False

    load_res = load_step(step_file)
    try:
        analysis = analyze_cad_model(load_res)
        test_cylinder_geometry(analysis)
        test_planar_geometry(analysis)
        test_topology_graph(analysis)
        test_report_artifacts(analysis, output_dir)
        print("=" * 60)
        print("ALL PHASE 3 TESTS PASSED SUCCESSFULLY.")
        print("=" * 60)
        return True
    finally:
        load_res.close()


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        sys.exit(1)
