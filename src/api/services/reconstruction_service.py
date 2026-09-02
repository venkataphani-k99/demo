"""Phase 19B — CAD Reconstruction Execution Service.

Wraps ReconstructionExecutor for use by the FastAPI layer, with workspace
management and artifact persistence.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.drawing.reconstruction_executor import ReconstructionExecutor, ReconstructionResult
from src.drawing.reconstruction_schemas import (
    CADOperationType,
    OperationValidity,
    ParametricReconstructionPlan,
)
from src.drawing.schemas import KnowledgeState

logger = logging.getLogger(__name__)


class ReconstructionService:
    """Service layer for Phase 19B CAD execution of 2D→3D reconstruction."""

    def __init__(self):
        self._executor = None  # Lazy init — requires FreeCAD runtime

    def _get_executor(self, partial_mode: bool = True) -> Optional[ReconstructionExecutor]:
        """Lazy-load the executor (FreeCAD import happens here)."""
        if self._executor is not None:
            self._executor.partial_mode = partial_mode
            return self._executor
        try:
            executor = ReconstructionExecutor(partial_mode=partial_mode)
            self._executor = executor
            return executor
        except Exception as exc:
            logger.error("Cannot create ReconstructionExecutor: %s", exc)
            return None

    def execute_reconstruction(
        self,
        plan: ParametricReconstructionPlan,
        workspace_path: str,
        partial_mode: bool = True,
    ) -> ReconstructionResult:
        """Execute a reconstruction plan and save artifacts.

        Parameters
        ----------
        plan : ParametricReconstructionPlan
            The Phase 19A blueprint to execute.
        workspace_path : str
            Workspace directory for saving output files.
        partial_mode : bool
            Allow PARTIALLY_EXECUTABLE steps with placeholder values.

        Returns
        -------
        ReconstructionResult
        """
        executor = self._get_executor(partial_mode=partial_mode)
        if executor is None:
            # Return a simulated result indicating FreeCAD is not available
            result = ReconstructionResult(
                project_id=plan.project_id,
                success=False,
                gate_status=plan.evidence_audit.gate_19b_status if plan.evidence_audit else "UNKNOWN",
                error_message=(
                    "FreeCAD is not available in this environment. "
                    "Install FreeCAD 1.0+ and ensure it is on PATH or set FREECAD_PATH."
                ),
            )
            # Still record step-by-step intent
            for step in plan.steps:
                from src.drawing.reconstruction_executor import ExecutionResult
                if step.operation_validity == OperationValidity.EXECUTABLE:
                    result.executable_count += 1
                elif step.operation_validity == OperationValidity.PARTIALLY_EXECUTABLE:
                    result.partial_count += 1
                elif step.knowledge_state == KnowledgeState.AMBIGUOUS:
                    result.skipped_count += 1
                elif step.execution_status.value == "BLOCKED_MISSING_PARAMETER":
                    result.skipped_count += 1
                else:
                    result.skipped_count += 1
            return result

        return executor.execute(plan, workspace_path=workspace_path)

    def dry_run(self, plan: ParametricReconstructionPlan) -> Dict[str, Any]:
        """Run a dry-run analysis without executing — summarize what would happen.

        Parameters
        ----------
        plan : ParametricReconstructionPlan

        Returns
        -------
        Dict with counts per validity class and per-operation breakdown.
        """
        steps_breakdown = []
        counts = {
            "executable": 0,
            "partially_executable": 0,
            "unconstrained": 0,
            "ambiguous": 0,
            "blocked": 0,
        }

        for step in plan.steps:
            validity = step.operation_validity.value
            if validity in counts:
                counts[validity.lower()] += 1
            else:
                counts["blocked"] += 1  # Default for unknowns

            steps_breakdown.append({
                "step_id": step.step_id,
                "operation": step.operation_type.value,
                "target": step.target_feature_id,
                "validity": validity,
                "known_params": step.known_parameters,
                "unknown_params": step.unknown_parameters,
                "blocking_reasons": step.unresolved_notes,
            })

        gate_passed = (
            plan.evidence_audit.gate_19b_passed
            if plan.evidence_audit
            else False
        )

        return {
            "project_id": plan.project_id,
            "reconstruction_status": plan.reconstruction_status.value,
            "gate_19b_passed": gate_passed,
            "gate_19b_status": plan.evidence_audit.gate_19b_status if plan.evidence_audit else "UNKNOWN",
            "gate_19b_rationale": plan.evidence_audit.gate_19b_rationale if plan.evidence_audit else "",
            "summary": counts,
            "steps": steps_breakdown,
            "recommendation": self._recommendation(counts, gate_passed),
        }

    @staticmethod
    def _recommendation(counts: Dict[str, int], gate_passed: bool) -> str:
        """Generate a human-readable recommendation string."""
        if gate_passed:
            return "All evidence constraints are satisfied. Ready for full CAD execution."
        total_blocked = counts["unconstrained"] + counts["ambiguous"] + counts["blocked"]
        if total_blocked == 0:
            return "No blocking issues — partial execution can proceed."
        issues = []
        if counts["unconstrained"]:
            issues.append(f"{counts['unconstrained']} unconstrained operations (missing center coordinates, depths, or edge selections)")
        if counts["ambiguous"]:
            issues.append(f"{counts['ambiguous']} ambiguous features (conflicting multi-model evidence)")
        if counts["blocked"]:
            issues.append(f"{counts['blocked']} blocked operations (missing prerequisite parameters)")
        return (
            f"Cannot fully reconstruct: {', '.join(issues)}. "
            "Resolve missing drawing evidence or enable partial_mode for best-effort reconstruction."
        )
