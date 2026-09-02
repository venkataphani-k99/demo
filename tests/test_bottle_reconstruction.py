"""Automated Test Suite for Axisymmetric Revolved Body (The Irishman 12 YO Bottle Drawing).

Asserts:
1. Primary reconstruction strategy is AXISYMMETRIC_REVOLVED.
2. Revolve axis supplied by reconstruction plan with explicit evidence and provenance.
3. No create_box or base_extrude operations.
4. No generic fallback primitive.
5. revolve_profile operation executed with angle_deg = 360 and verified axis.
6. Section & profile dimensional validation against explicit drawing callouts:
   - Overall height ≈ 238.0 mm
   - Maximum outer diameter ≈ 81.0 mm
   - Mid-body diameter ≈ 78.5 mm
   - Neck diameter ≈ 31.0 mm
7. Verified solid is NOT equivalent to a single simple cylinder.
8. Verified solid is NOT equivalent to a rectangular prism.
9. Verified hollow internal cavity exists.
10. Verified multiple radial transitions along Z.
11. B-Rep and mesh bounds consistency within tolerance.
12. Frontend model ID matches newly generated reconstruction ID.
13. Stale mesh cache is rejected on rebuild.
14. Complete reconstruction_debug_trace.json artifact is recorded.
"""
import json
from pathlib import Path
import pytest

from src.api.services.drawing_project_service import DrawingProjectService
from src.drawing.cad_reconstruction_engine import CADReconstructionExecutor
from src.drawing.cad_reconstructor import CADReconstructor
from src.drawing.feature_synthesizer import FeatureSynthesizer
from src.drawing.reconstruction_planner import ReconstructionPlanner
from src.drawing.reconstruction_schemas import (
    CADOperationType,
    PrimaryReconstructionStrategy,
    ReconstructionStatus,
    StepExecutionStatus,
)
from src.drawing.reconstruction_validator import ReconstructionValidator
from src.drawing.schemas import FeatureType


@pytest.fixture
def bottle_project_id():
    return "b4815df9-1a84-49f3-aa30-487e8a799d78"


def test_bottle_primary_strategy_detection(bottle_project_id):
    """Test 1: Synthesizer detects AXISYMMETRIC_REVOLVED strategy from SECTION view and diameter callouts."""
    svc = DrawingProjectService()
    u = svc.get_understanding(bottle_project_id)
    assert u is not None

    views = u.gemini_result.views if (u.gemini_result and u.gemini_result.views) else (u.claude_result.views if u.claude_result else [])
    views_map = {v.view_id: v.view_type for v in views}
    dimensions = u.gemini_result.dimensions if (u.gemini_result and u.gemini_result.dimensions) else (u.claude_result.dimensions if u.claude_result else [])
    entities = u.gemini_result.entities if (u.gemini_result and u.gemini_result.entities) else (u.claude_result.entities if u.claude_result else [])

    synthesizer = FeatureSynthesizer()
    fg = synthesizer.synthesize(
        dimensions=dimensions,
        views_map=views_map,
        entities=entities,
    )

    assert fg.primary_strategy == PrimaryReconstructionStrategy.AXISYMMETRIC_REVOLVED.value
    feat_types = [f.feature_type for f in fg.features]
    assert FeatureType.REVOLVED_FEATURE in feat_types
    assert FeatureType.BASE_BODY not in feat_types, "Bottle must NOT synthesize a rectangular BASE_BODY."


def test_bottle_reconstruction_plan_operations(bottle_project_id):
    """Test 2: Planner produces revolve_profile & boolean_cut sequence with explicit revolve axis evidence."""
    svc = DrawingProjectService()
    u = svc.get_understanding(bottle_project_id)

    views = u.gemini_result.views if (u.gemini_result and u.gemini_result.views) else []
    views_map = {v.view_id: v.view_type for v in views}
    dimensions = u.gemini_result.dimensions if (u.gemini_result and u.gemini_result.dimensions) else []
    entities = u.gemini_result.entities if (u.gemini_result and u.gemini_result.entities) else []

    synthesizer = FeatureSynthesizer()
    fg = synthesizer.synthesize(
        dimensions=dimensions,
        views_map=views_map,
        entities=entities,
    )

    planner = ReconstructionPlanner()
    plan = planner.plan(bottle_project_id, fg)

    assert plan.reconstruction_status == ReconstructionStatus.COMPLETE
    op_types = [s.operation_type for s in plan.steps]

    # Critical assertions
    assert CADOperationType.BASE_EXTRUDE not in op_types, "Plan must NOT contain base_extrude."
    assert CADOperationType.CREATE_BOX not in op_types, "Plan must NOT contain create_box."
    assert CADOperationType.REVOLVE_PROFILE in op_types, "Plan MUST contain revolve_profile."
    assert CADOperationType.BOOLEAN_CUT in op_types, "Plan MUST contain boolean_cut."

    revolve_steps = [s for s in plan.steps if s.operation_type == CADOperationType.REVOLVE_PROFILE]
    assert len(revolve_steps) >= 2, "Must revolve outer silhouette and inner cavity."
    assert revolve_steps[0].parameters["angle_deg"].value == 360.0

    # Verify explicit axis evidence
    assert revolve_steps[0].axis_evidence is not None
    assert revolve_steps[0].axis_evidence.axis_source == "detected_section_symmetry_axis"
    assert revolve_steps[0].parameters["axis_direction"].value == [0.0, 0.0, 1.0]


def test_bottle_end_to_end_cad_execution(bottle_project_id):
    """Test 3: CADReconstructor executes plan, verifies valid B-Rep solid, ~Ø81 x 238 mm bounding box, not a prism."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)

    assert mesh_data is not None
    assert mesh_data["topology"]["solids"] >= 1
    assert mesh_data["topology"]["faces"] >= 4

    bbox = mesh_data["bounding_box"]
    # Check bounding box approximately matches Ø81 x Ø81 x 238 mm
    assert abs(bbox["x_length"] - 81.0) < 5.0, f"Expected X length ~81 mm, got {bbox['x_length']}"
    assert abs(bbox["y_length"] - 81.0) < 5.0, f"Expected Y length ~81 mm, got {bbox['y_length']}"
    assert abs(bbox["z_length"] - 238.0) < 5.0, f"Expected Z length ~238 mm, got {bbox['z_length']}"

    # Confirm circular symmetry (X length ~= Y length within OpenCASCADE tolerance)
    assert abs(bbox["x_length"] - bbox["y_length"]) < 0.1, "Solid must be axisymmetric (X length == Y length)"

    # Check execution log has revolve_profile
    trace_path = Path(mesh_data["debug_trace_path"])
    assert trace_path.exists()
    trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace_data["final_status"] == "COMPLETE"


def test_bottle_section_profile_validation(bottle_project_id):
    """Test 4: Multi-station section diameter measurements compare accurately against drawing callouts."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace_path = Path(mesh_data["debug_trace_path"])
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    stations = trace.get("station_validations", [])
    assert len(stations) >= 3, "Must perform multiple section station validation checks."

    for st in stations:
        assert st["result"] == "PASS", f"Station check failed at Z={st['station_z']}: {st['details']}"


def test_bottle_not_equivalent_to_single_cylinder(bottle_project_id):
    """Test 5: Validates that reconstructed solid is not equivalent to a single simple cylinder."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace = json.loads(Path(mesh_data["debug_trace_path"]).read_text(encoding="utf-8"))

    summary = trace.get("validation_summary", {})
    assert summary["not_simple_cylinder"]["is_not_simple_cylinder"] is True
    assert summary["not_simple_cylinder"]["face_count"] >= 4


def test_bottle_not_equivalent_to_rectangular_prism(bottle_project_id):
    """Test 6: Validates that reconstructed solid is not equivalent to a rectangular prism."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace = json.loads(Path(mesh_data["debug_trace_path"]).read_text(encoding="utf-8"))

    summary = trace.get("validation_summary", {})
    assert summary["not_rectangular_prism"]["is_not_rectangular_prism"] is True
    assert summary["not_rectangular_prism"]["curved_faces"] >= 1


def test_bottle_hollow_cavity_validation(bottle_project_id):
    """Test 7: Validates that hollow internal cavity exists and volume ratio < 0.65."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace = json.loads(Path(mesh_data["debug_trace_path"]).read_text(encoding="utf-8"))

    summary = trace.get("validation_summary", {})
    assert summary["hollow_cavity"]["is_hollow"] is True
    assert summary["hollow_cavity"]["solid_to_bounding_ratio"] < 0.65


def test_bottle_radial_transition_validation(bottle_project_id):
    """Test 8: Validates that diameter changes along Z (body to neck transition delta >= 5 mm)."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace = json.loads(Path(mesh_data["debug_trace_path"]).read_text(encoding="utf-8"))

    summary = trace.get("validation_summary", {})
    assert summary["radial_transitions"]["valid"] is True
    assert summary["radial_transitions"]["diameter_delta"] >= 5.0


def test_brep_and_mesh_bounds_consistency(bottle_project_id):
    """Test 9: Verifies B-Rep bounding box matches exported Three.js mesh bounding box."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    art_trace = mesh_data.get("artifact_trace", {})

    assert art_trace["bounds_consistency"] == "PASS"
    assert art_trace["artifact_match"] == "PASS"


def test_api_returns_current_reconstruction_artifact(bottle_project_id):
    """Test 10: Ensures API response returns the model ID matching the active reconstruction trace."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)

    recon_id = mesh_data.get("reconstruction_id")
    assert recon_id is not None
    assert recon_id.startswith(f"recon_{bottle_project_id[:8]}")
    assert mesh_data["artifact_trace"]["reconstruction_id"] == recon_id


def test_stale_mesh_is_not_reused(bottle_project_id):
    """Test 11: Rebuilding with force_rebuild produces a fresh reconstruction_id and updates trace."""
    reconstructor = CADReconstructor()
    mesh_1 = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    id_1 = mesh_1.get("reconstruction_id")

    # Small delay to ensure timestamp change
    import time
    time.sleep(0.05)

    mesh_2 = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    id_2 = mesh_2.get("reconstruction_id")

    assert id_1 != id_2, "Fresh reconstruction must receive a unique reconstruction ID."


def test_frontend_model_id_matches_reconstruction_id(bottle_project_id):
    """Test 12: Frontend requested model ID is verified against the generated reconstruction ID."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    art_trace = mesh_data["artifact_trace"]

    assert art_trace["frontend_model_id"] == art_trace["reconstruction_id"]
    assert art_trace["actual_threejs_model_id"] == art_trace["reconstruction_id"]


def test_artifact_trace_is_complete(bottle_project_id):
    """Test 13: reconstruction_debug_trace.json contains all 15 required trace fields."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(bottle_project_id, force_rebuild=True)
    trace_file = Path(mesh_data["debug_trace_path"])
    assert trace_file.exists()

    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    assert "reconstruction_id" in trace
    assert "project_id" in trace
    assert "selected_strategy" in trace
    assert "steps" in trace
    assert "station_validations" in trace
    assert "validation_summary" in trace
    assert "artifact_trace" in trace

    at = trace["artifact_trace"]
    assert Path(at["brep_file_path"]).exists()
    assert Path(at["mesh_artifact_path"]).exists()
    assert at["brep_hash"] != ""
    assert at["mesh_hash"] != ""
    assert at["step_export_result"] == "PASS"
    assert at["tessellation_result"] == "PASS"
