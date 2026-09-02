"""Automated tests for robust CAD reconstruction artifact handling and error handling."""
import pytest
from src.drawing.cad_reconstructor import CADReconstructor
from src.drawing.reconstruction_schemas import (
    ParametricCADStep,
    ParametricReconstructionPlan,
    ReconstructionStatus,
    StepExecutionStatus,
    CADOperationType,
    FeatureType,
    SketchPlane,
    CADProfileType,
)


def test_unconstrained_plan_returns_structured_payload_without_crashing():
    """Validates that a reconstruction plan with unconstrained / blocked features returns a clean payload."""
    plan = ParametricReconstructionPlan(
        project_id="test_unconstrained_001",
        reconstruction_status=ReconstructionStatus.INSUFFICIENT_INFORMATION,
        steps=[
            ParametricCADStep(
                step_index=1,
                step_id="CAD_STEP_001",
                operation_type=CADOperationType.BASE_EXTRUDE,
                target_feature_id="FEAT_UNCONSTRAINED",
                target_feature_type=FeatureType.BASE_BODY,
                description="Unconstrained base",
                sketch_plane=SketchPlane.XY_TOP,
                profile_type=CADProfileType.UNKNOWN,
                execution_status=StepExecutionStatus.BLOCKED_MISSING_PARAMETER,
            )
        ]
    )

    reconstructor = CADReconstructor()
    mesh = reconstructor.reconstruct_from_plan("test_unconstrained_001", plan)

    assert mesh is not None
    assert mesh["topology"]["solids"] == 0
    assert mesh["solid"] is False
    assert mesh["status"] == "INSUFFICIENT_INFORMATION"
    assert "unconstrained" in mesh["message"].lower() or "insufficient" in mesh["message"].lower()
