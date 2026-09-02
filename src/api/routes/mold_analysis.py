"""Phase M1 — Manufacturing & Moldability Intelligence Engine API Router."""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status

from src.api.schemas import (
    EvaluateMoldDirectionRequest,
    ManufacturingReviewResponse,
    MoldAnalysisResponse,
)
from src.api.services.cad_service import CadService
from src.cad.mfg_presets import list_process_presets

router = APIRouter(tags=["Manufacturing / Moldability Intelligence Engine (Phase M1)"])
cad_service = CadService()


@router.get(
    "/manufacturing-presets",
    response_model=List[Dict[str, Any]],
    summary="List Available Manufacturing & Molding Process Presets",
)
def get_manufacturing_presets():
    """Returns configuration-driven process profiles (General Injection, Textured, Die Casting, SMC, LSR)."""
    return list_process_presets()


@router.get(
    "/projects/{project_id}/manufacturing-review",
    response_model=ManufacturingReviewResponse,
    summary="Get Complete Phase M1 Manufacturing Review Report",
)
def get_manufacturing_review(
    project_id: str,
    preset_id: str = "GENERAL_PLASTIC_INJECTION",
    force: bool = False,
):
    """Returns full deterministic B-Rep manufacturing analysis, pull direction ranking, undercuts, transverse core pins, wall thickness, and AI review."""
    try:
        return cad_service.get_manufacturing_review(project_id, preset_id=preset_id, force_refresh=force)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Manufacturing review failed: {e}")


@router.post(
    "/projects/{project_id}/manufacturing-review/evaluate",
    response_model=ManufacturingReviewResponse,
    summary="Dynamically Re-evaluate Manufacturing Review with Custom Direction & Preset",
)
def evaluate_manufacturing_direction(project_id: str, request: EvaluateMoldDirectionRequest):
    """Recomputes deterministic manufacturing findings, undercuts, and AI review along a user-specified draw vector."""
    try:
        return cad_service.evaluate_custom_mfg_review(
            project_id=project_id,
            direction=request.direction,
            min_draft_deg=request.min_draft_deg,
            cavity_pressure_bar=request.cavity_pressure_bar,
            preset_id=request.preset_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Direction evaluation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Backward Compatible Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/mold-analysis",
    response_model=MoldAnalysisResponse,
    summary="Get Phase 26 Injection Molding, Draft Angle, Undercut & Slider Analysis",
)
def get_mold_analysis(project_id: str, force: bool = False):
    """Returns Core/Cavity face classification, optimal pull axis, draft heatmap, true undercuts, parting lines, and side-action sliders."""
    try:
        return cad_service.get_mold_analysis(project_id, force_refresh=force)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Mold analysis failed: {e}")


@router.post(
    "/projects/{project_id}/mold-analysis/evaluate-direction",
    response_model=MoldAnalysisResponse,
    summary="Dynamically Re-evaluate Moldability with Custom Pull Direction & Draft Angle",
)
def evaluate_custom_mold_direction(project_id: str, request: EvaluateMoldDirectionRequest):
    """Recomputes face draft classifications, undercuts, and sliders along a user-specified 3D draw vector."""
    try:
        return cad_service.evaluate_custom_mold_direction(
            project_id=project_id,
            direction=request.direction,
            min_draft_deg=request.min_draft_deg,
            cavity_pressure_bar=request.cavity_pressure_bar,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Direction evaluation failed: {e}")
