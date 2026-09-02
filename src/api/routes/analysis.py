"""CAD analysis route."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import AnalysisSummarySchema
from src.api.services.cad_service import CadService

router = APIRouter(prefix="/projects", tags=["CAD Analysis"])
cad_service = CadService()


@router.post(
    "/{project_id}/analyze",
    response_model=AnalysisSummarySchema,
    summary="Execute Full CAD Analysis on Uploaded Model",
)
def analyze_cad_model(project_id: str):
    """Executes B-Rep topology inspection, geometric classification, exact CAD measurements, and feature recognition."""
    try:
        return cad_service.analyze_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"CAD analysis failed: {e}")


@router.get(
    "/{project_id}/mesh",
    summary="Get Exact 3D B-Rep Mesh and Wireframe Geometry for Three.js",
)
def get_project_mesh(project_id: str):
    """Returns exact 3D triangulated mesh, edge wireframes, and per-face mappings extracted from the STEP file."""
    try:
        return cad_service.get_mesh(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Mesh extraction failed: {e}")

