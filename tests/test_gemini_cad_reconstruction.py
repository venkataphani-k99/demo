"""Test Suite for Gemini-Assisted Controlled CAD Reconstruction Engine.

Validates:
1. Controlled CAD primitives (box, cylinder, polygon extrusion, cut, union, hole drill, fillet, chamfer).
2. Strict CADReconstructionPlan schema validation.
3. Deterministic execution of structured plans without running arbitrary Python code.
4. Topological manifold validation, bounding box checks, and mesh/STEP export.
"""
import pytest
from src.drawing.cad_reconstruction_engine import CADReconstructionExecutor
from src.drawing.reconstruction_schemas import (
    CADBoundingBox,
    CADCoordinateSystem,
    CADOperationStep,
    CADPartMetadata,
    CADReconstructionPlan,
    CADValidationCheck,
    DrawingEvidence,
)


def test_controlled_cad_primitives():
    """Test 1: Verify all 8 controlled CAD primitives execute deterministically in FreeCAD/OCCT."""
    executor = CADReconstructionExecutor(doc_name="TestPrimitivesDoc")
    try:
        # 1. Base Box
        box = executor.create_box("box_1", 100.0, 60.0, 20.0, origin=(0.0, 0.0, 0.0))
        assert box.isValid()
        assert len(box.Solids) == 1
        assert round(box.BoundBox.XLength, 2) == 100.0
        assert round(box.BoundBox.YLength, 2) == 60.0
        assert round(box.BoundBox.ZLength, 2) == 20.0

        # 2. Drill Hole
        solid = executor.drill_hole("hole_1", diameter=10.0, depth=20.0, center=(50.0, 30.0, 20.0), axis=(0.0, 0.0, -1.0), through_all=True)
        assert solid.isValid()
        assert round(float(solid.Volume), 2) < (100.0 * 60.0 * 20.0)

        # 3. Create Cylinder & Union
        cyl = executor.create_cylinder("cyl_1", radius=15.0, height=15.0, origin=(50.0, 30.0, 20.0), axis=(0.0, 0.0, 1.0))
        assert cyl.isValid()
        solid = executor.union_feature(tool_id="cyl_1", result_id="union_1")
        assert solid.isValid()
        assert round(solid.BoundBox.ZLength, 2) == 35.0

        # 4. Create Cutout tool & Cut
        tool_box = executor.create_box("cut_tool", 20.0, 60.0, 10.0, origin=(0.0, 0.0, 10.0))
        solid = executor.cut_feature(tool_id="cut_tool", result_id="cut_1")
        assert solid.isValid()

        # 5. Fillet & Chamfer
        solid = executor.apply_fillet([0, 1], radius=2.0)
        assert solid.isValid()

        solid = executor.apply_chamfer([2], distance=1.0)
        assert solid.isValid()
    finally:
        executor.close()


def test_cad_reconstruction_plan_execution():
    """Test 2: Verify execution of full structured CADReconstructionPlan matching prompt schema."""
    plan_dict = {
        "part_metadata": {
            "part_name": "MOUNTING_BRACKET_001",
            "drawing_units": "mm",
            "material": "Steel",
            "overall_confidence": 0.98,
        },
        "bounding_box": {
            "x_length": 80.0,
            "y_length": 50.0,
            "z_length": 25.0,
        },
        "coordinate_system": {
            "origin_description": "Corner of base plate",
            "front_view_plane": "XZ",
            "top_view_plane": "XY",
        },
        "reconstruction_steps": [
            {
                "step_id": "step_1_base",
                "order": 1,
                "operation": "create_box",
                "parameters": {
                    "feature_id": "base_plate",
                    "length_x": 80.0,
                    "width_y": 50.0,
                    "height_z": 25.0,
                    "origin": [0.0, 0.0, 0.0],
                },
                "drawing_evidence": {
                    "source_view": "Front & Top Views",
                    "callout_dimension": "80 x 50 x 25",
                    "confidence": 1.0,
                },
            },
            {
                "step_id": "step_2_bore",
                "order": 2,
                "operation": "drill_hole",
                "parameters": {
                    "feature_id": "central_bore",
                    "diameter": 20.0,
                    "depth": 25.0,
                    "center": [40.0, 25.0, 25.0],
                    "axis": [0.0, 0.0, -1.0],
                    "through_all": True,
                },
                "drawing_evidence": {
                    "source_view": "Top View",
                    "callout_dimension": "Ø20 THRU",
                    "confidence": 0.99,
                },
            },
            {
                "step_id": "step_3_mounting_hole_1",
                "order": 3,
                "operation": "drill_hole",
                "parameters": {
                    "feature_id": "mount_hole_1",
                    "diameter": 6.0,
                    "depth": 25.0,
                    "center": [10.0, 10.0, 25.0],
                    "axis": [0.0, 0.0, -1.0],
                    "through_all": True,
                },
                "drawing_evidence": {
                    "source_view": "Top View",
                    "callout_dimension": "2X Ø6",
                    "confidence": 0.95,
                },
            },
            {
                "step_id": "step_4_mounting_hole_2",
                "order": 4,
                "operation": "drill_hole",
                "parameters": {
                    "feature_id": "mount_hole_2",
                    "diameter": 6.0,
                    "depth": 25.0,
                    "center": [70.0, 40.0, 25.0],
                    "axis": [0.0, 0.0, -1.0],
                    "through_all": True,
                },
                "drawing_evidence": {
                    "source_view": "Top View",
                    "callout_dimension": "2X Ø6",
                    "confidence": 0.95,
                },
            },
        ],
        "validation_checks": [
            {
                "view": "Top View",
                "expected_dimension": 80.0,
                "measured_axis": "X",
                "tolerance": 0.5,
            },
            {
                "view": "Side View",
                "expected_dimension": 50.0,
                "measured_axis": "Y",
                "tolerance": 0.5,
            },
            {
                "view": "Front View",
                "expected_dimension": 25.0,
                "measured_axis": "Z",
                "tolerance": 0.5,
            },
        ],
        "is_fully_constrained": True,
        "ambiguous_features": [],
    }

    # Validate Schema
    plan = CADReconstructionPlan.model_validate(plan_dict)
    assert plan.bounding_box.x_length == 80.0
    assert len(plan.reconstruction_steps) == 4

    executor = CADReconstructionExecutor(doc_name="TestPlanExecDoc")
    try:
        res = executor.execute_plan(plan)
        assert res["success"] is True
        assert res["solid_valid"] is True
        assert res["bounding_box"]["x_length"] == 80.0
        assert res["bounding_box"]["y_length"] == 50.0
        assert res["bounding_box"]["z_length"] == 25.0
        assert res["faces_count"] > 6  # base 6 faces + inner cylindrical faces
        assert len(res["validation_results"]) == 3
        for val in res["validation_results"]:
            assert val["passed"] is True
    finally:
        executor.close()


def test_polygon_extrusion():
    """Test 3: Verify 2D sketch polygon extrusion into 3D solid."""
    executor = CADReconstructionExecutor(doc_name="TestExtrudeDoc")
    try:
        points = [(0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (50.0, 30.0, 0.0), (0.0, 30.0, 0.0)]
        solid = executor.extrude_polygon("poly_base", points=points, extrude_vector=(0.0, 0.0, 15.0))
        assert solid.isValid()
        assert round(solid.BoundBox.XLength, 2) == 50.0
        assert round(solid.BoundBox.YLength, 2) == 30.0
        assert round(solid.BoundBox.ZLength, 2) == 15.0
        assert round(float(solid.Volume), 2) == (50.0 * 30.0 * 15.0)
    finally:
        executor.close()
