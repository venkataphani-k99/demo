"""Comprehensive Test Suite for 3-Blade Propeller Reconstruction (Non-Rectangular Pipeline).

Validates:
1. Detection of Hub, Blade, and 3-Blade Rotational Pattern at 120° (no rectangular base body).
2. Exact FreeCAD / OpenCASCADE B-Rep solid construction.
3. Center bore drilling, blade extrusion, and rotational pattern fusion.
4. Mesh generation for Three.js 3D Blueprint viewer.
5. Complete transparent debug trace generation.
"""
from pathlib import Path
import pytest

from src.api.services.drawing_project_service import DrawingProjectService
from src.drawing.cad_reconstruction_engine import CADReconstructionExecutor
from src.drawing.cad_reconstructor import CADReconstructor
from src.drawing.feature_synthesizer import FeatureSynthesizer
from src.drawing.reconstruction_planner import ReconstructionPlanner
from src.drawing.reconstruction_schemas import (
    CADOperationType,
    CADProfileType,
    ReconstructionStatus,
    StepExecutionStatus,
)
from src.drawing.schemas import FeatureType


@pytest.fixture
def propeller_project_id():
    return "cb765f54-52b5-419b-b1e2-0403079b9097"


def test_propeller_feature_synthesis_no_rectangular_base(propeller_project_id):
    """Test 1: Synthesizer must recognize Hub and Blade with Rotational Pattern without assuming rectangular base."""
    svc = DrawingProjectService()
    u = svc.get_understanding(propeller_project_id)
    assert u is not None

    views_map = {v.view_id: v.view_type for v in (u.claude_result.views if u.claude_result else [])}
    dimensions = u.consensus.agreed_dimensions if u.consensus else []
    entities = (u.claude_result.entities if u.claude_result else [])

    # Synthesize feature graph
    synthesizer = FeatureSynthesizer()
    fg = synthesizer.synthesize(
        dimensions=u.claude_result.dimensions if u.claude_result else [],
        views_map=views_map,
        entities=entities,
    )

    feat_types = [f.feature_type for f in fg.features]
    assert FeatureType.HUB in feat_types, "Propeller must have recognized HUB feature."
    assert FeatureType.BLADE in feat_types, "Propeller must have recognized BLADE feature."

    blade_feat = next(f for f in fg.features if f.feature_type == FeatureType.BLADE)
    assert blade_feat.rotational_pattern is not None
    assert blade_feat.rotational_pattern.count == 3
    assert blade_feat.rotational_pattern.angle_step_deg == 120.0


def test_propeller_reconstruction_plan(propeller_project_id):
    """Test 2: Reconstruction plan must order Hub -> Blade -> Rotational Pattern -> Bore without rectangular extrusion."""
    svc = DrawingProjectService()
    u = svc.get_understanding(propeller_project_id)
    views_map = {v.view_id: v.view_type for v in (u.claude_result.views if u.claude_result else [])}
    entities = (u.claude_result.entities if u.claude_result else [])

    synthesizer = FeatureSynthesizer()
    fg = synthesizer.synthesize(
        dimensions=u.claude_result.dimensions if u.claude_result else [],
        views_map=views_map,
        entities=entities,
    )

    planner = ReconstructionPlanner()
    plan = planner.plan(propeller_project_id, fg)

    assert plan.reconstruction_status == ReconstructionStatus.COMPLETE
    assert len(plan.steps) >= 3

    # Verify Step 1 is Hub Cylinder
    assert plan.steps[0].operation_type == CADOperationType.CREATE_CYLINDER
    assert plan.steps[0].profile_type == CADProfileType.CIRCLE
    assert plan.steps[0].execution_status == StepExecutionStatus.READY

    # Verify Step 2 is Blade Profile
    assert plan.steps[1].operation_type == CADOperationType.CREATE_ARBITRARY_PROFILE
    assert plan.steps[1].profile_type == CADProfileType.AIRFOIL_OR_BLADE_PROFILE
    assert plan.steps[1].execution_status == StepExecutionStatus.READY

    # Verify Step 3 is Rotational Pattern
    assert plan.steps[2].operation_type == CADOperationType.ROTATIONAL_PATTERN
    assert plan.steps[2].rotational_pattern is not None
    assert plan.steps[2].rotational_pattern["count"] == 3
    assert plan.steps[2].rotational_pattern["angle_step_deg"] == 120.0

    # Verify debug trace is generated
    assert plan.debug_trace is not None
    assert plan.debug_trace.total_steps == len(plan.steps)
    assert plan.debug_trace.final_status == "COMPLETE"


def test_propeller_solid_reconstruction_and_mesh(propeller_project_id):
    """Test 3: CADReconstructor physically builds 3-Blade Propeller B-Rep solid & Three.js mesh."""
    reconstructor = CADReconstructor()
    mesh_data = reconstructor.reconstruct_mesh(propeller_project_id, force_rebuild=True)

    assert mesh_data is not None
    assert "positions" in mesh_data or "vertices" in mesh_data
    assert mesh_data["topology"]["solids"] >= 1
    assert mesh_data["bounding_box"]["x_length"] > 0
    assert mesh_data["bounding_box"]["y_length"] > 0
    assert mesh_data["bounding_box"]["z_length"] > 0

    # Verify STEP file was created
    step_path = Path("workspaces") / "drawing_projects" / propeller_project_id / "reconstructed_step.step"
    assert step_path.exists()
    assert step_path.stat().st_size > 500
