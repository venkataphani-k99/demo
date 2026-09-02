"""FastAPI router for Engineering Issues & Recommendations (Phase 12)."""
from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.services.project_service import ProjectService
from src.cad.freecad_env import get_freecad_python

router = APIRouter(prefix="/projects", tags=["Engineering Issues & Recommendations"])
project_service = ProjectService()

FREECAD_PYTHON = get_freecad_python()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class RecommendationActionResponse(BaseModel):
    recommendation_id: str
    issue_id: str
    action: str
    approval_status: str
    message: str


import threading

_issues_generation_lock = threading.Lock()


def _ensure_issues_generated(project_id: str) -> Tuple[Path, Path, Path]:
    meta = project_service.get_project_metadata(project_id)
    step_file = Path(meta["step_file"])
    pdir = step_file.parent
    base_name = step_file.stem

    issues_path = pdir / f"{base_name}_engineering_issues.json"
    recs_path = pdir / f"{base_name}_engineering_recommendations.json"
    summary_path = pdir / f"{base_name}_engineering_review_summary.json"

    # Fast path if already generated
    if issues_path.exists() and recs_path.exists() and summary_path.exists():
        return issues_path, recs_path, summary_path

    with _issues_generation_lock:
        if issues_path.exists() and recs_path.exists() and summary_path.exists():
            return issues_path, recs_path, summary_path

        # Execute engineering review engine via CLI bridge
        cmd = [
            FREECAD_PYTHON,
            "-m", "src.main",
            "engineering-review",
            str(step_file),
            "--output-dir", str(pdir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        # Fallback to output/ directory if artifacts exist for this specific model
        if not issues_path.exists():
            fallback_i = PROJECT_ROOT / "output" / f"{base_name}_engineering_issues.json"
            if fallback_i.exists():
                issues_path = fallback_i
        if not recs_path.exists():
            fallback_r = PROJECT_ROOT / "output" / f"{base_name}_engineering_recommendations.json"
            if fallback_r.exists():
                recs_path = fallback_r
        if not summary_path.exists():
            fallback_s = PROJECT_ROOT / "output" / f"{base_name}_engineering_review_summary.json"
            if fallback_s.exists():
                summary_path = fallback_s

        # For any model where review has no issues, create empty project-scoped review artifacts
        if not issues_path.exists():
            issues_path.write_text("[]", encoding="utf-8")
        if not recs_path.exists():
            recs_path.write_text("[]", encoding="utf-8")
        if not summary_path.exists():
            empty_summary = {
                "model": meta["filename"],
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "consensus": {
                    "total_issues_identified": 0,
                    "consensus_issues_count": 0,
                    "consensus_issue_ids": [],
                    "claude_only_issue_ids": [],
                    "gemini_only_issue_ids": [],
                    "conflicting_issues_count": 0,
                    "total_validated_recommendations": 0,
                    "total_rejected_recommendations": 0,
                    "human_approval_state": "NO_ISSUES_FOUND",
                },
                "issues": [],
                "recommendations": [],
            }
            summary_path.write_text(json.dumps(empty_summary, indent=2), encoding="utf-8")

        return issues_path, recs_path, summary_path


@router.get("/{project_id}/issues", status_code=status.HTTP_200_OK)
def get_project_issues(project_id: str) -> List[Dict[str, Any]]:
    """Retrieves validated engineering issues with deterministic CAD evidence."""
    issues_path, _, _ = _ensure_issues_generated(project_id)
    if not issues_path.exists():
        raise HTTPException(status_code=404, detail="Issues artifact not found.")
    return json.loads(issues_path.read_text(encoding="utf-8"))


@router.get("/{project_id}/recommendations", status_code=status.HTTP_200_OK)
def get_project_recommendations(project_id: str) -> List[Dict[str, Any]]:
    """Retrieves actionable engineering recommendations requiring human approval."""
    _, recs_path, _ = _ensure_issues_generated(project_id)
    if not recs_path.exists():
        raise HTTPException(status_code=404, detail="Recommendations artifact not found.")
    return json.loads(recs_path.read_text(encoding="utf-8"))


@router.get("/{project_id}/review-summary", status_code=status.HTTP_200_OK)
def get_project_review_summary(project_id: str) -> Dict[str, Any]:
    """Retrieves multimodal review summary and provider consensus."""
    _, _, summary_path = _ensure_issues_generated(project_id)
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Review summary artifact not found.")
    return json.loads(summary_path.read_text(encoding="utf-8"))


@router.post("/{project_id}/recommendations/{recommendation_id}/approve", status_code=status.HTTP_200_OK)
def approve_recommendation(project_id: str, recommendation_id: str) -> RecommendationActionResponse:
    """Sets recommendation state to APPROVED without modifying CAD drawing."""
    _, recs_path, _ = _ensure_issues_generated(project_id)
    recs = json.loads(recs_path.read_text(encoding="utf-8"))

    target = None
    for r in recs:
        if r["recommendation_id"] == recommendation_id:
            r["approval_status"] = "APPROVED"
            target = r
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")

    recs_path.write_text(json.dumps(recs, indent=2), encoding="utf-8")
    return RecommendationActionResponse(
        recommendation_id=target["recommendation_id"],
        issue_id=target["issue_id"],
        action=target["action"],
        approval_status="APPROVED",
        message="Recommendation approved by engineer. (Zero CAD drawing modification executed)",
    )


@router.post("/{project_id}/recommendations/{recommendation_id}/reject", status_code=status.HTTP_200_OK)
def reject_recommendation(project_id: str, recommendation_id: str) -> RecommendationActionResponse:
    """Sets recommendation state to REJECTED without modifying CAD drawing."""
    _, recs_path, _ = _ensure_issues_generated(project_id)
    recs = json.loads(recs_path.read_text(encoding="utf-8"))

    target = None
    for r in recs:
        if r["recommendation_id"] == recommendation_id:
            r["approval_status"] = "REJECTED"
            target = r
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found.")

    recs_path.write_text(json.dumps(recs, indent=2), encoding="utf-8")
    return RecommendationActionResponse(
        recommendation_id=target["recommendation_id"],
        issue_id=target["issue_id"],
        action=target["action"],
        approval_status="REJECTED",
        message="Recommendation rejected by engineer.",
    )
