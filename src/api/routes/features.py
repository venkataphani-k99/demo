"""Recognized CAD features route."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import FeatureListResponse
from src.api.services.cad_service import CadService

router = APIRouter(prefix="/projects", tags=["Features"])
cad_service = CadService()


@router.get(
    "/{project_id}/features",
    response_model=FeatureListResponse,
    summary="Get Recognized CAD Engineering Features",
)
def get_recognized_features(project_id: str):
    """Returns deterministic engineering features (counterbores, holes, bosses, fillets) extracted from the 3D model."""
    try:
        return cad_service.get_features(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
