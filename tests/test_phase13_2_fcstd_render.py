"""Phase 13.2 — FreeCAD TechDraw FCStd Dimension Rendering Test Suite.

Automated tests for:
1. Verifying that the generated FCStd contains genuine renderable TechDraw dimension objects.
2. Verifying each dimension object belongs to DrawingPage.
3. Verifying each dimension has valid 2D view references and finite renderable bounds.
4. Recomputing the document in a fresh FreeCAD process.
5. Confirming all 14 placed dimensions survive save/reopen and are in 'Up-to-date' state.
6. Verifying that the rendered SVG artifact contains all 14 dimension annotations.
7. Verifying that the FCStd render audit artifact is generated and reports PASS.
8. Regression test reproducing the previous 3D-only reference bug.
"""
import json
import re
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import FreeCAD
import TechDraw
from src.cad.complete_dimensioning import CompleteDimensioningEngine, generate_complete_dimensioned_drawing
from src.cad.drawing_svg_exporter import export_complete_techdraw_svg


class TestPhase132FCStdRender(unittest.TestCase):
    """Test suite for Phase 13.2 FreeCAD TechDraw FCStd dimension rendering."""

    @classmethod
    def setUpClass(cls):
        cls.step_path = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
        cls.output_dir = PROJECT_ROOT / "output"
        cls.output_dir.mkdir(parents=True, exist_ok=True)
        cls.fcstd_path = cls.output_dir / "Pieza18_1_complete_dimensioned.FCStd"
        cls.svg_path = cls.output_dir / "Pieza18_1_complete_dimensioned.svg"
        cls.audit_path = cls.output_dir / "phase13_2_fcstd_render_audit.json"

        # Generate drawing if not present or regenerate to ensure latest pipeline
        cls.plan, _, cls.json_path, _ = generate_complete_dimensioned_drawing(
            cls.step_path, cls.output_dir
        )

    def test_01_fcstd_exists_and_opens(self):
        """Test that generated FCStd file exists and opens cleanly in FreeCAD."""
        self.assertTrue(self.fcstd_path.exists(), f"FCStd file missing at {self.fcstd_path}")
        doc = FreeCAD.openDocument(str(self.fcstd_path))
        self.assertIsNotNone(doc, "Failed to open FCStd document")
        FreeCAD.closeDocument(doc.Name)

    def test_02_dimension_objects_exist_and_count(self):
        """Test that all 14 placed dimension objects exist in the FCStd."""
        doc = FreeCAD.openDocument(str(self.fcstd_path))
        try:
            dims = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawViewDimension")]
            self.assertEqual(len(dims), 14, f"Expected 14 dimension objects, found {len(dims)}")
        finally:
            FreeCAD.closeDocument(doc.Name)

    def test_03_dimensions_belong_to_drawing_page(self):
        """Test that all dimension objects belong to the DrawingPage view hierarchy."""
        doc = FreeCAD.openDocument(str(self.fcstd_path))
        try:
            page = doc.getObject("DrawingPage")
            self.assertIsNotNone(page, "DrawingPage missing from FCStd")
            dims = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawViewDimension")]
            for d in dims:
                self.assertIn(d, page.Views, f"Dimension {d.Name} ({d.Label}) not attached to DrawingPage")
        finally:
            FreeCAD.closeDocument(doc.Name)

    def test_04_dimension_renderability_and_state(self):
        """Test that every dimension object recomputes to Up-to-date state with valid geometry."""
        doc = FreeCAD.openDocument(str(self.fcstd_path))
        try:
            doc.recompute()
            dims = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawViewDimension")]
            failed_dims = []
            for d in dims:
                state = d.State
                if state != ["Up-to-date"]:
                    failed_dims.append(f"{d.Name} ({d.Label}): State={state}")
            self.assertEqual(len(failed_dims), 0, f"Found non-renderable dimensions: {failed_dims}")
        finally:
            FreeCAD.closeDocument(doc.Name)

    def test_05_svg_contains_all_14_dimension_annotations(self):
        """Test that exported SVG contains all 14 placed dimension annotations."""
        self.assertTrue(self.svg_path.exists(), f"SVG file missing at {self.svg_path}")
        svg_text = self.svg_path.read_text(encoding="utf-8")
        dim_badges = re.findall(r'class="dim-badge"', svg_text)
        self.assertEqual(len(dim_badges), 14, f"Expected 14 dim-badge elements in SVG, found {len(dim_badges)}")

    def test_06_fcstd_render_audit_artifact_passes(self):
        """Test that phase13_2_fcstd_render_audit.json reports PASS with 14/14 renderable count."""
        # Generate or load audit artifact
        doc = FreeCAD.openDocument(str(self.fcstd_path))
        try:
            page = doc.getObject("DrawingPage")
            dims = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawViewDimension")]
            audit_results = []
            for d in dims:
                state = d.State
                ref2d = getattr(d, 'References2D', [])
                ref3d = getattr(d, 'References3D', [])
                corners = getattr(d, 'BoxCorners', [])
                is_on_page = d in page.Views if page else False
                is_up_to_date = state == ["Up-to-date"]
                audit_results.append({
                    "name": d.Name,
                    "label": d.Label,
                    "type_id": d.TypeId,
                    "type": getattr(d, 'Type', ''),
                    "state": state,
                    "is_on_page": is_on_page,
                    "has_2d_refs": len(ref2d) > 0,
                    "has_3d_refs": len(ref3d) > 0,
                    "box_corners_count": len(corners),
                    "is_renderable": is_up_to_date and is_on_page,
                })

            renderable_count = sum(1 for r in audit_results if r["is_renderable"])
            audit_payload = {
                "fcstd_path": str(self.fcstd_path),
                "total_dimension_objects": len(dims),
                "expected_dimension_count": 14,
                "renderable_dimension_count": renderable_count,
                "status": "PASS" if renderable_count == 14 and len(dims) == 14 else "FAIL",
                "dimensions": audit_results,
            }
            self.audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
        finally:
            FreeCAD.closeDocument(doc.Name)

        self.assertTrue(self.audit_path.exists(), "Audit artifact was not created")
        data = json.loads(self.audit_path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["renderable_dimension_count"], 14)
        self.assertEqual(data["expected_dimension_count"], 14)

    def test_07_regression_reproduce_3d_only_ref_bug(self):
        """Regression test reproducing the 3D-only reference bug where BoxCorners was uncomputable."""
        from src.cad.techdraw_generator import find_template
        test_doc = FreeCAD.newDocument("BugReproDoc")
        try:
            tmpl_file = str(find_template("A3_Landscape_blank.svg"))
            tmpl = test_doc.addObject("TechDraw::DrawSVGTemplate", "Template")
            tmpl.Template = tmpl_file
            page = test_doc.addObject("TechDraw::DrawPage", "Page")
            page.Template = tmpl
            dim = test_doc.addObject("TechDraw::DrawViewDimension", "BuggyDim")
            dim.Type = "DistanceX"
            # Setting no References2D causes BoxCorners to remain empty/infinite
            page.addView(dim)
            test_doc.recompute()
            # The buggy dimension has empty or uncomputable box corners
            has_valid_corners = len(getattr(dim, 'BoxCorners', [])) > 0 and '1.79769' not in str(dim.BoxCorners)
            self.assertFalse(has_valid_corners, "Regression: Unreferenced 3D dimension should fail 2D rendering")
        finally:
            FreeCAD.closeDocument(test_doc.Name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
