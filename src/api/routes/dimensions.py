"""Engineering dimensions and coverage route."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import DimensionListResponse
from src.api.services.cad_service import CadService

router = APIRouter(prefix="/projects", tags=["Dimensions"])
cad_service = CadService()


@router.get(
    "/{project_id}/dimensions",
    response_model=DimensionListResponse,
    summary="Get Complete Engineering Dimension Candidates & Feature Coverage",
)
def get_dimension_candidates(project_id: str):
    """Returns candidate dimensions, dependencies, redundancy classifications, view assignments, and feature coverage."""
    try:
        return cad_service.get_dimensions(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
