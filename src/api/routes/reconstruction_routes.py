"""Phase 19B — FastAPI routes for 2D→3D CAD reconstruction execution."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import (
    ExecutionRequest,
    ExecutionResponse,
    ReconstructionPlanRequest,
    ReconstructionPlanResponse,
)
from src.api.services.drawing_project_service import DrawingProjectService
from src.api.services.reconstruction_service import ReconstructionService

router = APIRouter(prefix="/drawing-projects", tags=["CAD Reconstruction (Phase 19B)"])
_svc = DrawingProjectService()
_recon_svc = ReconstructionService()


# ---------------------------------------------------------------------------
# POST /drawing-projects/{id}/reconstruct — Execute 19B CAD reconstruction
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/reconstruct",
    response_model=ExecutionResponse,
    summary="Execute Phase 19B CAD Reconstruction (2D → 3D FreeCAD Geometry)",
)
def execute_reconstruction(
    project_id: str,
    request: ExecutionRequest = ExecutionRequest(),
) -> Dict[str, Any]:
    """Execute the Phase 19B reconstruction: translate the 19A parametric blueprint
    into actual FreeCAD geometry.

    Flow:
    1. Load or generate the Phase 19A reconstruction plan (runs planner + auditor).
    2. Check the Hard 19B Gate.
    3. Execute EXECUTABLE operations in order, skipping unconstrained/ambiguous ones.
    4. If partial_mode=True, PARTIALLY_EXECUTABLE operations run with placeholder values.
    5. Save the resulting FCStd document and STEP file to the project workspace.

    Query params:
    - partial_mode (bool): Enable partial execution (default: True).
    """
    try:
        meta = _svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    pdir = _svc.get_project_dir(project_id)

    # Load or generate the 19A plan
    try:
        plan = _svc.get_reconstruction_plan(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot get reconstruction plan: {exc}. Run /analyze first.",
        )

    # Execute Phase 19B
    try:
        result = _recon_svc.execute_reconstruction(
            plan=plan,
            workspace_path=str(pdir),
            partial_mode=request.partial_mode,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Phase 19B execution failed: {exc}",
        )

    # Update metadata
    status_str = "reconstructed" if result.success else "reconstruction_partial"
    _svc.update_status(project_id, status_str)

    # Save execution results as JSON
    try:
        result_json = {
            "project_id": result.project_id,
            "success": result.success,
            "gate_passed": result.gate_passed,
            "gate_status": result.gate_status,
            "executable_count": result.executable_count,
            "partial_count": result.partial_count,
            "skipped_count": result.skipped_count,
            "failed_count": result.failed_count,
            "error_message": result.error_message,
            "created_at": result.created_at,
            "steps": [
                {
                    "step_id": sr.step_id,
                    "operation": sr.operation_type,
                    "success": sr.success,
                    "error": sr.error_message,
                    "warnings": sr.warnings,
                    "skipped_reason": sr.skipped_reason,
                }
                for sr in result.step_results
            ],
        }
        import json
        result_path = pdir / "19b_execution_result.json"
        result_path.write_text(json.dumps(result_json, indent=2), encoding="utf-8")
        _svc._save_meta(project_id, {
            **_svc._load_meta(project_id),
            "artifacts": {
                **_svc._load_meta(project_id).get("artifacts", {}),
                "19b_execution_result": {
                    "artifact_id": "19b_execution_result",
                    "filename": result_path.name,
                    "file_path": str(result_path),
                    "artifact_type": "execution_result_json",
                },
            },
        })
    except Exception:
        pass

    return {
        "project_id": result.project_id,
        "success": result.success,
        "gate_passed": result.gate_passed,
        "gate_status": result.gate_status,
        "executable_count": result.executable_count,
        "partial_count": result.partial_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "error_message": result.error_message,
        "created_at": result.created_at,
        "summary": result.summary(),
    }


# ---------------------------------------------------------------------------
# POST /drawing-projects/{id}/reconstruct/dry-run — Analyze without executing
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/reconstruct/dry-run",
    summary="Dry-Run Phase 19B Analysis (No FreeCAD Execution)",
)
def dry_run_reconstruction(project_id: str) -> Dict[str, Any]:
    """Analyze the reconstruction plan and report what would happen during
    execution, without actually running FreeCAD operations.

    Useful for assessing gate status and understanding which features are
    blocked before committing to a full CAD reconstruction.
    """
    try:
        meta = _svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    try:
        plan = _svc.get_reconstruction_plan(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot get reconstruction plan: {exc}. Run /analyze first.",
        )

    dry_run = _recon_svc.dry_run(plan)
    return dry_run


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/reconstruct/result — Get last execution result
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/reconstruct/result",
    summary="Get Last Phase 19B Execution Result",
)
def get_execution_result(project_id: str) -> Dict[str, Any]:
    """Returns the last Phase 19B execution result, if available."""
    try:
        meta = _svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    artifacts = meta.get("artifacts", {})
    result_artifact = artifacts.get("19b_execution_result")
    if not result_artifact:
        raise HTTPException(
            status_code=404,
            detail="No Phase 19B execution result found. Run /reconstruct first.",
        )

    import json
    result_path = Path(result_artifact["file_path"])
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Execution result file missing on disk.")

    return json.loads(result_path.read_text(encoding="utf-8"))
