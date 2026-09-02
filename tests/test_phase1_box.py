"""Phase 1: Simple FreeCAD Geometry Creation and Measurement Test.

Validates that FreeCAD can be initialized in headless Python,
create a document, generate a solid box (100 x 60 x 20 mm),
inspect its exact B-Rep bounding box dimensions, and close the document cleanly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Initialize FreeCAD environment
import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part


def run_box_test() -> bool:
    doc_name = "Phase1_Box_Test"
    print("=" * 60)
    print("PHASE 1 — FREECAD SOLID GEOMETRY TEST")
    print("=" * 60)
    print(f"FreeCAD Version : {'.'.join(FreeCAD.Version()[:3])}")
    print(f"Python Version  : {sys.version.split()[0]}")
    print("-" * 60)

    # 1. Create a new FreeCAD document
    doc = FreeCAD.newDocument(doc_name)
    try:
        # 2. Define intended box dimensions
        target_length = 100.0  # mm
        target_width = 60.0    # mm
        target_height = 20.0   # mm

        # 3. Create a 3D box solid using Part module
        # Part.makeBox(length, width, height) creates a solid B-Rep shape
        box_shape = Part.makeBox(target_length, target_width, target_height)
        
        # Add the shape as an object in the document
        box_obj = doc.addObject("Part::Feature", "TestBox")
        box_obj.Shape = box_shape
        doc.recompute()

        # 4. Read the exact geometry from the B-Rep shape
        shape = box_obj.Shape
        bbox = shape.BoundBox

        # Extract measured dimensions
        measured_length = bbox.XLength
        measured_width = bbox.YLength
        measured_height = bbox.ZLength

        print("FreeCAD test successful\n")
        print("Box:")
        print(f"Length = {measured_length:.1f} mm")
        print(f"Width = {measured_width:.1f} mm")
        print(f"Height = {measured_height:.1f} mm")
        print("-" * 60)
        print(f"Solid count     : {len(shape.Solids)}")
        print(f"Face count      : {len(shape.Faces)}")
        print(f"Edge count      : {len(shape.Edges)}")
        print(f"Vertex count    : {len(shape.Vertexes)}")
        print(f"Bounding Box Min: ({bbox.XMin:.1f}, {bbox.YMin:.1f}, {bbox.ZMin:.1f}) mm")
        print(f"Bounding Box Max: ({bbox.XMax:.1f}, {bbox.YMax:.1f}, {bbox.ZMax:.1f}) mm")
        print("=" * 60)

        # 5. Assertions for engineering truth
        assert abs(measured_length - target_length) < 1e-6, f"Length mismatch: {measured_length} vs {target_length}"
        assert abs(measured_width - target_width) < 1e-6, f"Width mismatch: {measured_width} vs {target_width}"
        assert abs(measured_height - target_height) < 1e-6, f"Height mismatch: {measured_height} vs {target_height}"
        assert len(shape.Solids) == 1, f"Expected 1 solid, got {len(shape.Solids)}"
        assert len(shape.Faces) == 6, f"Expected 6 faces, got {len(shape.Faces)}"
        assert len(shape.Edges) == 12, f"Expected 12 edges, got {len(shape.Edges)}"
        assert len(shape.Vertexes) == 8, f"Expected 8 vertices, got {len(shape.Vertexes)}"

        return True

    finally:
        # 6. Cleanly close document without leaking memory
        FreeCAD.closeDocument(doc_name)


if __name__ == "__main__":
    success = run_box_test()
    if not success:
        sys.exit(1)
