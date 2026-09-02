"""AI Engineering Review router (Phase 11)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from src.api.schemas import AIReviewRequest, AIReviewResponse, AIRecommendationSchema, DrawingArtifactSchema
from src.api.services.project_service import ProjectService
from src.cad.freecad_env import get_freecad_python

router = APIRouter(prefix="/projects", tags=["AI Engineering Review"])
project_service = ProjectService()

FREECAD_PYTHON = get_freecad_python()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@router.post(
    "/{project_id}/ai-review",
    response_model=AIReviewResponse,
    summary="Execute Live Multimodal AI Engineering Review",
)
def execute_ai_review(project_id: str, request: AIReviewRequest = AIReviewRequest()):
    """Executes multimodal engineering review using the selected provider (mock, claude, gemini).

    Strictly adheres to deterministic CAD source of truth and validation gatekeeper.
    """
    try:
        meta = project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent

        # Execute review via CLI bridge
        cmd = [
            FREECAD_PYTHON,
            "-m", "src.main",
            "ai-review",
            str(step_file),
            "--output-dir", str(pdir),
            "--provider", request.provider,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            err_msg = res.stderr or res.stdout
            if "not set" in err_msg or "environment variable" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"API key missing for provider '{request.provider}'. {err_msg.strip()}",
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"AI review execution failed: {err_msg.strip()}",
            )

        base_name = step_file.stem
        review_json_path = pdir / f"{base_name}_ai_review.json"
        review_txt_path = pdir / f"{base_name}_ai_review.txt"

        if not review_json_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Review JSON artifact was not generated",
            )

        # Register artifacts
        artifacts = [
            project_service.register_artifact(project_id, "ai_review_json", "json", review_json_path),
            project_service.register_artifact(project_id, "ai_review_txt", "txt", review_txt_path),
        ]

        data = json.loads(review_json_path.read_text(encoding="utf-8"))

        return AIReviewResponse(
            project_id=project_id,
            review_id=data.get("review_id", "REV-UNKNOWN"),
            provider=data.get("provider", request.provider),
            model=data.get("model", "unknown"),
            overall_assessment=data.get("overall_assessment", "good"),
            good_aspects=data.get("good_aspects", []),
            improvement_areas=data.get("improvement_areas", []),
            recommendations=[
                AIRecommendationSchema(**r) for r in data.get("recommendations", [])
            ],
            warnings=data.get("warnings", []),
            requires_human_review=data.get("requires_human_review", False),
            stats=data.get("stats", {}),
            artifacts=artifacts,
        )

    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{project_id}/ai-review",
    response_model=AIReviewResponse,
    summary="Get Existing AI Engineering Review for Project",
)
def get_existing_ai_review(project_id: str):
    """Retrieves existing engineering review results for a project."""
    try:
        meta = project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent
        base_name = step_file.stem
        review_json_path = pdir / f"{base_name}_ai_review.json"
        review_txt_path = pdir / f"{base_name}_ai_review.txt"

        if not review_json_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No AI review has been performed yet for project '{project_id}'",
            )

        artifacts = []
        if review_json_path.exists():
            artifacts.append(project_service.register_artifact(project_id, "ai_review_json", "json", review_json_path))
        if review_txt_path.exists():
            artifacts.append(project_service.register_artifact(project_id, "ai_review_txt", "txt", review_txt_path))

        data = json.loads(review_json_path.read_text(encoding="utf-8"))

        return AIReviewResponse(
            project_id=project_id,
            review_id=data.get("review_id", "REV-UNKNOWN"),
            provider=data.get("provider", "mock"),
            model=data.get("model", "unknown"),
            overall_assessment=data.get("overall_assessment", "good"),
            good_aspects=data.get("good_aspects", []),
            improvement_areas=data.get("improvement_areas", []),
            recommendations=[
                AIRecommendationSchema(**r) for r in data.get("recommendations", [])
            ],
            warnings=data.get("warnings", []),
            requires_human_review=data.get("requires_human_review", False),
            stats=data.get("stats", {}),
            artifacts=artifacts,
        )

    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
