"""Drawing generation routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import DrawingGenerateRequest, DrawingResponse
from src.api.services.drawing_service import DrawingService

router = APIRouter(prefix="/projects", tags=["Drawings"])
drawing_service = DrawingService()


@router.post(
    "/{project_id}/drawings",
    response_model=DrawingResponse,
    summary="Generate Standard 5-View TechDraw Orthographic Drawing",
)
def generate_standard_drawing(project_id: str, request: DrawingGenerateRequest = DrawingGenerateRequest()):
    """Generates standard 5-view (Front, Top, Left, Right, Bottom) TechDraw drawing and exports FCStd, SVG, and DXF."""
    try:
        return drawing_service.generate_standard_drawing(
            project_id=project_id,
            projection=request.projection,
            template=request.template,
            scale=request.scale,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Drawing generation failed: {e}")


@router.post(
    "/{project_id}/dimensioned-drawing",
    response_model=DrawingResponse,
    summary="Generate Complete Dimensioned TechDraw Drawing (Phase 9A)",
)
def generate_complete_dimensioned_drawing(project_id: str):
    """Executes full Phase 9A pipeline: views, non-colliding dimension placement, 3D validation, and artifact exports."""
    try:
        return drawing_service.generate_dimensioned_drawing(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dimensioned drawing generation failed: {e}")
