"""Phase 19A.2 — Automated Test Suite for Reconstruction Evidence Gate.

Validates that:
1. Every CAD_STEP in the reconstruction plan has an evidence audit record.
2. Every EXECUTABLE operation has location evidence.
3. Every EXECUTABLE operation has direction evidence.
4. Every EXECUTABLE subtractive operation has termination evidence.
5. Every fillet has explicit target-edge evidence (cannot be EXECUTABLE if edge is unconstrained).
6. Ambiguous features cannot become EXECUTABLE.
7. Base height_z remains unconstrained without promoting arbitrary dimensions.
8. Holes and bosses without center coordinates or extrusion heights cannot become EXECUTABLE.
9. Hard 19B Gate is strictly LOCKED when any missing parameters or unconstrained operations exist.
10. Strict provenance (Tier A -> Tier B -> Tier C -> Tier D) is preserved across all operations.
"""
import pytest

from src.api.services.drawing_project_service import DrawingProjectService
from src.drawing.reconstruction_auditor import ReconstructionAuditor
from src.drawing.reconstruction_planner import ReconstructionPlanner
from src.drawing.reconstruction_schemas import (
    CADOperationType,
    OperationValidity,
    ParametricReconstructionPlan,
    ReconstructionStatus,
    StepExecutionStatus,
)


@pytest.fixture
def benchmark_plan():
    """Load and audit the benchmark drawing reconstruction plan (Pieza18_1)."""
    svc = DrawingProjectService()
    proj_id = "6f8683f4-fec2-44e2-901b-84de173aea94"
    u = svc.get_understanding(proj_id)
    assert u.feature_graph is not None, "FeatureGraph must exist for benchmark drawing."
    planner = ReconstructionPlanner()
    plan = planner.plan(proj_id, u.feature_graph)
    return plan


def test_every_cad_step_has_evidence_audit_record(benchmark_plan: ParametricReconstructionPlan):
    """Test 1: Every CAD_STEP must have an auditable EvidenceAuditRecord."""
    assert len(benchmark_plan.steps) > 0
    assert benchmark_plan.evidence_audit is not None
    assert len(benchmark_plan.evidence_audit.records) == len(benchmark_plan.steps)

    for step in benchmark_plan.steps:
        assert step.evidence_audit is not None, f"Step {step.step_id} missing evidence audit."
        assert step.evidence_audit.step_id == step.step_id
        assert step.evidence_audit.target_feature_id == step.target_feature_id
        assert step.evidence_audit.validity is not None


def test_executable_operations_require_full_evidence(benchmark_plan: ParametricReconstructionPlan):
    """Test 2: Any EXECUTABLE operation MUST have confirmed location, direction, and topology."""
    for step in benchmark_plan.steps:
        audit = step.evidence_audit
        if audit.validity == OperationValidity.EXECUTABLE:
            assert audit.location_status == "CONSTRAINED", f"Executable step {step.step_id} missing location evidence."
            assert audit.direction_status == "CONSTRAINED", f"Executable step {step.step_id} missing direction evidence."
            assert audit.target_topology_status == "DERIVED", f"Executable step {step.step_id} missing target topology."


def test_subtractive_operations_require_termination_evidence(benchmark_plan: ParametricReconstructionPlan):
    """Test 3: Subtractive operations cannot be EXECUTABLE without through-all or blind depth."""
    for step in benchmark_plan.steps:
        if step.operation_type in (CADOperationType.HOLE_DRILL, CADOperationType.CUT_EXTRUDE):
            audit = step.evidence_audit
            if audit.validity == OperationValidity.EXECUTABLE:
                assert audit.termination_type in ("THROUGH_ALL", "BLIND")
                assert audit.termination_evidence is not None


def test_fillet_requires_explicit_target_edge_evidence(benchmark_plan: ParametricReconstructionPlan):
    """Test 4: Fillet radius callout alone is NOT sufficient; target edge selection must be derived."""
    fillet_steps = [s for s in benchmark_plan.steps if s.operation_type == CADOperationType.EDGE_FILLET]
    assert len(fillet_steps) > 0, "Benchmark must contain at least one fillet step."

    for step in fillet_steps:
        audit = step.evidence_audit
        assert audit.magnitude_name == "radius"
        assert audit.magnitude_value_mm == 2.0
        # In 2D drawing without explicit 3D edge identity, fillet must NOT be EXECUTABLE
        assert audit.target_topology_status == "UNCONSTRAINED"
        assert audit.validity != OperationValidity.EXECUTABLE
        assert "target_edge_selection" in step.unknown_parameters


def test_ambiguous_features_cannot_become_executable(benchmark_plan: ParametricReconstructionPlan):
    """Test 5: Ambiguous features (e.g. FEAT_014 / 3.98 mm) are strictly blocked/ambiguous."""
    ambig_steps = [s for s in benchmark_plan.steps if s.target_feature_id == "FEAT_014"]
    assert len(ambig_steps) > 0, "Benchmark must contain ambiguous step FEAT_014."

    for step in ambig_steps:
        assert step.operation_validity == OperationValidity.AMBIGUOUS
        assert step.evidence_audit.validity == OperationValidity.AMBIGUOUS
        assert step.execution_status == StepExecutionStatus.SKIPPED_AMBIGUOUS


def test_base_height_remains_unconstrained_without_guessing(benchmark_plan: ParametricReconstructionPlan):
    """Test 6: Base height_z is NOT guessed as 50 mm; remains unconstrained."""
    base_step = next(s for s in benchmark_plan.steps if s.operation_type == CADOperationType.BASE_EXTRUDE)
    assert base_step.parameters["width_x"].value == 70.04
    assert base_step.parameters["depth_y"].value == 50.0
    assert base_step.parameters["height_z"].value is None
    assert "height_z" in benchmark_plan.unconstrained_parameters
    assert base_step.evidence_audit.validity in (OperationValidity.PARTIALLY_EXECUTABLE, OperationValidity.BLOCKED)


def test_bosses_and_holes_without_location_are_unconstrained(benchmark_plan: ParametricReconstructionPlan):
    """Test 7: Bosses (Ø30, Ø16) and Holes (Ø11, Ø5.5) without center coordinates are UNCONSTRAINED."""
    cyl_steps = [
        s for s in benchmark_plan.steps
        if s.operation_type in (CADOperationType.HOLE_DRILL, CADOperationType.BOSS_EXTRUDE)
    ]
    for step in cyl_steps:
        assert step.evidence_audit.location_status == "UNCONSTRAINED"
        assert step.evidence_audit.validity in (OperationValidity.UNCONSTRAINED, OperationValidity.BLOCKED)
        assert step.evidence_audit.validity != OperationValidity.EXECUTABLE


def test_hard_19b_gate_locked_when_evidence_missing(benchmark_plan: ParametricReconstructionPlan):
    """Test 8: Hard 19B Gate is strictly LOCKED (gate_19b_passed == False)."""
    audit = benchmark_plan.evidence_audit
    assert audit is not None
    assert audit.gate_19b_passed is False
    assert audit.gate_19b_status == "HARD_GATE_LOCKED_MISSING_EVIDENCE"
    assert audit.executable_count == 0
    assert audit.unconstrained_count >= 1
    assert "locked" in audit.gate_19b_rationale.lower()


def test_strict_four_tier_provenance_preserved(benchmark_plan: ParametricReconstructionPlan):
    """Test 9: Every audit record contains full Tier A -> Tier B -> Tier C -> Tier D provenance."""
    for step in benchmark_plan.steps:
        p = step.evidence_audit.provenance_chain
        assert "tier_a_entities" in p
        assert "tier_a_dimensions" in p
        assert "tier_b_feature" in p
        assert "tier_c_graph_node" in p
        assert "tier_d_proposed_op" in p
        assert p["tier_b_feature"]["feature_id"] == step.target_feature_id
