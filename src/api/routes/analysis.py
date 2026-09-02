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


@router.get(
    "/{project_id}/engineering-intelligence",
    summary="Get Phase 20 Engineering Design Intelligence & Verification Report",
)
def get_engineering_intelligence(project_id: str):
    """Returns exact B-Rep audit, 12 core question answers, feature graph, view scores, section cuts, and provenanced dimensions."""
    try:
        return cad_service.get_engineering_intelligence(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Engineering intelligence failed: {e}")


@router.get(
    "/{project_id}/ai-engineering-review",
    summary="Get Phase 24 AI Engineering Design Review",
)
def get_ai_engineering_review(project_id: str, force: bool = False):
    """Returns grounded AI engineering review with 5 prioritized inspection items, feature explanations, and validated evidence."""
    try:
        return cad_service.get_ai_engineering_review(project_id, force_refresh=force)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI engineering review failed: {e}")


@router.post(
    "/{project_id}/ai-engineering-question",
    summary="Ask Natural Language Question Grounded in CAD B-Rep Evidence",
)
def ask_ai_engineering_question(project_id: str, payload: dict):
    """Answers engineering design review questions grounded in OCCT geometry truth with validated provenance."""
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")
    try:
        return cad_service.ask_ai_engineering_question(project_id, question)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI engineering Q&A failed: {e}")


@router.get(
    "/{project_id}/cad-drawing-consistency",
    summary="Get Phase 25 CAD ↔ Engineering Drawing Consistency Audit",
)
def get_cad_drawing_consistency(project_id: str, force: bool = False):
    """Returns deterministic CAD ↔ Drawing matches, consistency classifications, dimension coverage, and AI explanations."""
    try:
        return cad_service.get_cad_drawing_consistency(project_id, force_refresh=force)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"CAD ↔ Drawing consistency audit failed: {e}")


@router.post(
    "/{project_id}/cad-drawing-question",
    summary="Ask Engineering Question about CAD vs Drawing Consistency",
)
def ask_cad_drawing_question(project_id: str, payload: dict):
    """Answers engineering consistency questions grounded in CAD facts and drawing evidence."""
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")
    try:
        return cad_service.ask_cad_drawing_question(project_id, question)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"CAD ↔ Drawing Q&A failed: {e}")



