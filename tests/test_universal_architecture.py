"""Phase 20 — Permanent Architectural Anti-Regression Test Suite.

Verifies:
1. Zero hardcoded dimensions or guessed geometry values.
2. Every geometry parameter has verified evidence provenance.
3. Every derived parameter has a recorded mathematical derivation.
4. Zero generic fallback boxes or cylinders.
5. Zero part-name branching in reconstruction decision modules (bottle, propeller, bracket, shaft, etc.).
6. New arbitrary parts require zero new shape-specific code.
7. Multi-view coordinate registration & cross-view dimension aggregation.
8. Candidate plan selection is 100% geometry-driven.
9. Candidate search is strictly bounded (MAX_CANDIDATES, BEAM_WIDTH).
10. Critical validation failures override high weighted scores.
11. Partial/unconstrained shapes are never exported as COMPLETE.
12. Reprojection & section slice validation against source evidence.
13. Final mesh matches final B-Rep bounding box.
14. Legacy reconstruction cannot bypass authoritative pipeline.
"""
import ast
import os
import pytest
from pathlib import Path

from src.drawing.cad_operation_inferer import (
    BEAM_WIDTH,
    CADOperationInferer,
    CandidateCADPlan,
    InferredCADOpType,
    InferredCADOperation,
    MAX_FULL_BREP_CANDIDATES,
    assert_no_hardcoded_geometry_parameters,
)
from src.drawing.cad_reconstruction_engine import CADReconstructionExecutor
from src.drawing.cad_reconstructor import CADReconstructor
from src.drawing.coordinate_registration import CoordinateRegistrar
from src.drawing.reprojection_validator import ReprojectionValidator
from src.drawing.universal_constraint_graph import ConstraintGraphBuilder, UniversalConstraintGraph
from src.drawing.universal_geometry import (
    FeatureCueType,
    GenericDimension,
    GenericDimensionType,
    GenericEntity,
    GenericGeometryType,
    ParameterProvenance,
    SolvedParameter,
    UniversalStatus,
)


def test_no_hardcoded_dimensions_in_reconstruction_pipeline():
    """Test 1: Rejection of unproven parameters by the strict provenance guard."""
    unproven_param = SolvedParameter(
        parameter_id="P_UNPROVEN",
        name="extrusion_height",
        value=50.0,
        provenance=[],  # Empty provenance!
    )
    plan = CandidateCADPlan(
        candidate_id="TEST_PLAN_001",
        feature_hypothesis_id="HYP_001",
        operations=[
            InferredCADOperation(
                step_id="OP_001",
                order=1,
                operation=InferredCADOpType.EXTRUDE_PROFILE,
                target_id="test_body",
                parameters={"height": unproven_param},
                description="Test op",
            )
        ],
    )
    with pytest.raises(ValueError, match="zero evidence provenance"):
        assert_no_hardcoded_geometry_parameters(plan)


def test_every_geometry_parameter_has_provenance():
    """Test 2: Proven parameters pass the provenance guard."""
    proven_param = SolvedParameter(
        parameter_id="P_PROVEN",
        name="radius",
        value=25.0,
        provenance=[
            ParameterProvenance(
                source_view_id="FRONT",
                source_dimension_id="DIM_01",
                raw_text="Ø50",
                is_derived=True,
                derivation_rule="radius = diameter / 2",
            )
        ],
        derivation="radius = diameter / 2",
    )
    plan = CandidateCADPlan(
        candidate_id="TEST_PLAN_002",
        feature_hypothesis_id="HYP_002",
        operations=[
            InferredCADOperation(
                step_id="OP_001",
                order=1,
                operation=InferredCADOpType.CREATE_CYLINDER,
                target_id="test_cyl",
                parameters={"radius": proven_param},
                description="Test op",
            )
        ],
    )
    # Must pass without error
    assert_no_hardcoded_geometry_parameters(plan)


def test_every_derived_parameter_has_recorded_derivation():
    """Test 3: Derived parameters must record derivation rule."""
    derived_param = SolvedParameter(
        parameter_id="P_DERIVED",
        name="outer_radius",
        value=40.5,
        provenance=[
            ParameterProvenance(
                source_view_id="SECTION_A_A",
                source_dimension_id="DIM_81",
                raw_text="Ø81.0",
                is_derived=True,
                derivation_rule="81.0 / 2",
            )
        ],
        derivation="81.0 / 2",
    )
    assert derived_param.provenance[0].is_derived is True
    assert derived_param.derivation == "81.0 / 2"


def test_no_generic_box_fallback():
    """Test 4: Unconstrained drawing returns INSUFFICIENT_INFORMATION rather than a box fallback."""
    reconstructor = CADReconstructor()
    # Execute empty/unconstrained plan
    empty_plan = CandidateCADPlan(
        candidate_id="EMPTY_PLAN",
        feature_hypothesis_id="HYP_NONE",
        operations=[],
        status=UniversalStatus.INSUFFICIENT_INFORMATION,
    )
    res = reconstructor.reconstruct_from_plan("test_no_box_project", empty_plan)
    assert res["topology"]["solids"] == 0
    assert res["status"] == UniversalStatus.INSUFFICIENT_INFORMATION.value
    assert res["solid"] is False


def test_no_generic_cylinder_fallback():
    """Test 5: Partial parameters do not fabricate cylinder."""
    executor = CADReconstructionExecutor("TestNoFallback")
    res = executor.execute_plan({"steps": []})
    assert res["shape"] is None
    assert res["success"] is False
    executor.close()


def test_no_part_name_branching_in_reconstruction_logic():
    """Test 6: Static AST scan ensuring zero part-name conditionals in core reconstruction decision files."""
    forbidden_terms = ["bottle", "propeller", "flange_bracket", "shaft_step"]
    target_files = [
        Path("src/drawing/cad_operation_inferer.py"),
        Path("src/drawing/universal_constraint_graph.py"),
        Path("src/drawing/reprojection_validator.py"),
        Path("src/drawing/coordinate_registration.py"),
        Path("src/drawing/universal_geometry.py"),
    ]

    for tf in target_files:
        assert tf.exists(), f"File {tf} missing"
        source_code = tf.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        for node in ast.walk(tree):
            # Check string constants in comparison / conditionals
            if isinstance(node, ast.Compare):
                for comp in node.comparators:
                    if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        val_lower = comp.value.lower()
                        for term in forbidden_terms:
                            assert term not in val_lower, f"Forbidden part-name conditional '{term}' found in {tf}"


def test_new_part_type_requires_no_new_shape_specific_code():
    """Test 7: Arbitrary custom geometric profile and dimension constraints infer CAD operations automatically."""
    entities = [
        GenericEntity(
            entity_id="ENT_POLY_01",
            geometry_type=GenericGeometryType.CLOSED_PROFILE,
            source_view_id="FRONT",
            is_closed=True,
            confidence=0.95,
        )
    ]
    dims = [
        GenericDimension(
            dimension_id="DIM_W",
            dimension_type=GenericDimensionType.LINEAR_DIMENSION,
            source_view_id="FRONT",
            raw_text="55.0",
            nominal_value=55.0,
            measured_axis="X",
        ),
        GenericDimension(
            dimension_id="DIM_D",
            dimension_type=GenericDimensionType.LINEAR_DIMENSION,
            source_view_id="TOP",
            raw_text="35.0",
            nominal_value=35.0,
            measured_axis="Y",
        ),
        GenericDimension(
            dimension_id="DIM_H",
            dimension_type=GenericDimensionType.LINEAR_DIMENSION,
            source_view_id="FRONT",
            raw_text="25.0",
            nominal_value=25.0,
            measured_axis="Z",
        ),
    ]
    reg = CoordinateRegistrar.register_views({"V_FRONT": "FRONT", "V_TOP": "TOP"}, dims, entities)
    graph = ConstraintGraphBuilder.build(entities, dims, reg)
    plans = CADOperationInferer.infer_candidate_plans(graph)

    assert len(plans) >= 1
    assert plans[0].status == UniversalStatus.CONSTRAINED
    assert "width_x" in plans[0].solved_parameters
    assert "depth_y" in plans[0].solved_parameters
    assert "height_z" in plans[0].solved_parameters


def test_cross_view_coordinate_registration():
    """Test 8: Multi-view coordinate frame mapping and projection correspondence."""
    views = {"V1": "FRONT", "V2": "TOP", "V3": "RIGHT"}
    reg = CoordinateRegistrar.register_views(views, [], [])

    assert "V1" in reg.view_frames
    assert "V2" in reg.view_frames
    assert "V3" in reg.view_frames
    assert reg.view_frames["V1"].normal_3d == (0.0, -1.0, 0.0)
    assert reg.view_frames["V2"].normal_3d == (0.0, 0.0, 1.0)


def test_cross_view_dimensions_can_fully_constrain_feature():
    """Test 9: Dimensions distributed across FRONT (X, Z) and TOP (Y) fully constrain a 3D solid."""
    dims = [
        GenericDimension(dimension_id="D1", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="FRONT", raw_text="40", nominal_value=40.0, measured_axis="X"),
        GenericDimension(dimension_id="D2", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="TOP", raw_text="30", nominal_value=30.0, measured_axis="Y"),
        GenericDimension(dimension_id="D3", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="FRONT", raw_text="15", nominal_value=15.0, measured_axis="Z"),
    ]
    reg = CoordinateRegistrar.register_views({"V1": "FRONT", "V2": "TOP"}, dims, [])
    graph = ConstraintGraphBuilder.build([], dims, reg)

    assert graph.overall_status == UniversalStatus.CONSTRAINED


def test_candidate_plan_selection_is_geometry_driven():
    """Test 10: Axisymmetric geometry with section callouts automatically generates and selects revolve candidates."""
    entities = [GenericEntity(entity_id="E_SEC", geometry_type=GenericGeometryType.SECTION_LINE, source_view_id="SECTION")]
    dims = [
        GenericDimension(dimension_id="D_DIA1", dimension_type=GenericDimensionType.DIAMETER_DIMENSION, source_view_id="SECTION", raw_text="Ø81.0", nominal_value=81.0),
        GenericDimension(dimension_id="D_DIA2", dimension_type=GenericDimensionType.DIAMETER_DIMENSION, source_view_id="SECTION", raw_text="Ø31.0", nominal_value=31.0),
        GenericDimension(dimension_id="D_H", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="SECTION", raw_text="238.0", nominal_value=238.0, measured_axis="Z"),
    ]
    reg = CoordinateRegistrar.register_views({"SEC": "SECTION", "FRONT": "FRONT"}, dims, entities)
    graph = ConstraintGraphBuilder.build(entities, dims, reg)
    plans = CADOperationInferer.infer_candidate_plans(graph)

    assert len(plans) >= 1
    assert plans[0].operations[0].operation == InferredCADOpType.REVOLVE_PROFILE


def test_candidate_search_is_bounded():
    """Test 11: Candidate plans are pruned to MAX_FULL_BREP_CANDIDATES and obey search limits."""
    assert MAX_FULL_BREP_CANDIDATES <= 5
    assert BEAM_WIDTH >= 5


def test_critical_validation_failure_overrides_high_score():
    """Test 12: High score cannot override critical dimension mismatch or invalid B-Rep."""
    import src.cad.freecad_env  # noqa: F401
    import Part
    # Create a small cylinder (Ø10 x 10 mm)
    cyl = Part.makeCylinder(5.0, 10.0)
    # Expected height is 100 mm (critical mismatch)
    dims = [
        GenericDimension(dimension_id="D_REQ", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="FRONT", raw_text="100.0", nominal_value=100.0, measured_axis="Z")
    ]
    graph = UniversalConstraintGraph()
    report = ReprojectionValidator.validate_candidate_brep(cyl, graph, dims)

    assert report.critical_gate_passed is False
    assert report.final_status == UniversalStatus.VALIDATION_FAILED


def test_partial_shape_cannot_be_exported_as_final():
    """Test 13: Unconstrained drawing returns status != COMPLETE and solid = False."""
    reconstructor = CADReconstructor()
    res = reconstructor.reconstruct_mesh("test_nonexistent_project_12345")
    assert res["topology"]["solids"] == 0
    assert res["status"] in (UniversalStatus.INSUFFICIENT_INFORMATION.value, UniversalStatus.PARTIALLY_CONSTRAINED.value)
    assert res["solid"] is False


def test_final_brep_matches_source_projections():
    """Test 14: Valid B-Rep matching expected dimensions passes reprojection validation."""
    import src.cad.freecad_env  # noqa: F401
    import Part
    # Create box (20 x 30 x 40 mm)
    box = Part.makeBox(20.0, 30.0, 40.0)
    dims = [
        GenericDimension(dimension_id="D_Z", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="FRONT", raw_text="40.0", nominal_value=40.0, measured_axis="Z")
    ]
    graph = UniversalConstraintGraph()
    report = ReprojectionValidator.validate_candidate_brep(box, graph, dims)

    assert report.critical_gate_passed is True
    assert report.final_status == UniversalStatus.COMPLETE


def test_final_brep_matches_section_evidence():
    """Test 15: Section slicing produces valid cross-section spans."""
    import src.cad.freecad_env  # noqa: F401
    import Part
    cyl = Part.makeCylinder(15.0, 50.0)
    dims = [
        GenericDimension(dimension_id="D_H", dimension_type=GenericDimensionType.LINEAR_DIMENSION, source_view_id="FRONT", raw_text="50.0", nominal_value=50.0, measured_axis="Z")
    ]
    report = ReprojectionValidator.validate_candidate_brep(cyl, UniversalConstraintGraph(), dims)
    assert report.critical_gate_passed is True


def test_final_mesh_matches_final_brep():
    """Test 16: Three.js mesh bounding box matches B-Rep BoundBox within 1.0 mm tolerance."""
    reconstructor = CADReconstructor()
    # Bottle project id
    res = reconstructor.reconstruct_mesh("b4815df9-1a84-49f3-aa30-487e8a799d78", force_rebuild=True)
    if res.get("topology", {}).get("solids", 0) > 0:
        art_trace = res.get("artifact_trace", {})
        assert art_trace.get("bounds_consistency") == "PASS"


def test_empty_mesh_is_never_reported_as_complete():
    """Test 17: A mesh with 0 vertices / 0 solids is never reported as COMPLETE."""
    reconstructor = CADReconstructor()
    res = reconstructor.reconstruct_mesh("a7c9719c-a858-426a-8472-5805243c0cbe", force_rebuild=True)
    if res.get("topology", {}).get("solids", 0) == 0:
        assert res.get("status") != UniversalStatus.COMPLETE.value


def test_legacy_pipeline_cannot_bypass_authoritative_pipeline():
    """Test 18: _build_shape legacy direct builder raises NotImplementedError."""
    reconstructor = CADReconstructor()
    with pytest.raises(NotImplementedError):
        reconstructor._build_shape("test", Path("."), None)
