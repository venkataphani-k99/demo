"""Phase 21 — FastAPI routes for downstream Moldability Analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from src.api.services.drawing_project_service import DrawingProjectService
from src.api.services.project_service import ProjectService
from src.cad.step_loader import load_step
from src.mold_analysis.engine import MoldAnalysisEngine
from src.mold_analysis.schemas import MoldAnalysisResult, MoldParameters

router = APIRouter(tags=["Mold Analysis"])
_drawing_svc = DrawingProjectService()
_project_svc = ProjectService()
_engine = MoldAnalysisEngine()


# ---------------------------------------------------------------------------
# UC2 Drawing Projects Mold Analysis Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/drawing-projects/{project_id}/mold-analysis",
    response_model=MoldAnalysisResult,
    summary="Get or Compute Mold Analysis for 2D-to-3D Reconstructed B-Rep",
)
def get_drawing_project_mold_analysis(
    project_id: str,
    direction: Optional[str] = Query(None, description="Optional opening direction label e.g. +Z, -Z, +Y"),
    min_draft: Optional[float] = Query(None, description="Optional minimum draft angle in degrees"),
) -> MoldAnalysisResult:
    """Retrieves or executes geometric moldability analysis on the validated 2D-to-3D reconstructed B-Rep."""
    pdir = _drawing_svc.get_project_dir(project_id)
    if not pdir.exists():
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    step_path = pdir / "reconstructed_step.step"

    # If step file does not exist yet, attempt automatic reconstruction from understanding if available
    if not step_path.exists() or step_path.stat().st_size == 0:
        try:
            from src.drawing.cad_reconstructor import CADReconstructor
            CADReconstructor().reconstruct_mesh(project_id)
        except Exception:
            pass

    if not step_path.exists() or step_path.stat().st_size == 0:
        # Validated B-Rep does not exist
        return MoldAnalysisResult(
            analysis_id=f"mold_unavailable_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["A validated 3D B-Rep model is required before mold analysis."],
        )

    # Load shape from reconstructed STEP
    load_res = load_step(step_path)
    shape = load_res.primary_shape
    if not shape:
        load_res.close()
        return MoldAnalysisResult(
            analysis_id=f"mold_failed_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["Reconstructed STEP file contains no primary 3D solid body."],
        )

    try:
        content = step_path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()

        # Build parameters
        params = MoldParameters()
        if min_draft is not None:
            params.minimum_draft_angle = min_draft
            params.user_configured_fields.append("minimum_draft_angle")
        if direction:
            dir_map = {
                "+z": [0.0, 0.0, 1.0], "-z": [0.0, 0.0, -1.0],
                "+y": [0.0, 1.0, 0.0], "-y": [0.0, -1.0, 0.0],
                "+x": [1.0, 0.0, 0.0], "-x": [-1.0, 0.0, 0.0],
            }
            if direction.lower() in dir_map:
                params.mold_opening_direction = dir_map[direction.lower()]
                params.direction_label = direction
                params.user_configured_fields.append("mold_opening_direction")

        res = _engine.analyze(
            shape=shape,
            mold_parameters=params,
            reconstruction_id=project_id,
            artifact_hash=sha256,
            source_filename=step_path.name,
            source_type="2D_RECONSTRUCTED_BREP",
        )

        # Save to cache
        out_json = pdir / "mold_analysis.json"
        out_json.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        return res
    finally:
        load_res.close()


@router.post(
    "/drawing-projects/{project_id}/mold-analysis",
    response_model=MoldAnalysisResult,
    summary="Execute Configured Mold Analysis for 2D-to-3D Reconstructed B-Rep",
)
def run_drawing_project_mold_analysis(
    project_id: str,
    params: MoldParameters,
) -> MoldAnalysisResult:
    """Executes geometric mold analysis with custom manufacturing parameters on reconstructed B-Rep."""
    pdir = _drawing_svc.get_project_dir(project_id)
    if not pdir.exists():
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    step_path = pdir / "reconstructed_step.step"
    if not step_path.exists() or step_path.stat().st_size == 0:
        return MoldAnalysisResult(
            analysis_id=f"mold_unavailable_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["A validated 3D B-Rep model is required before mold analysis."],
        )

    load_res = load_step(step_path)
    shape = load_res.primary_shape
    if not shape:
        load_res.close()
        return MoldAnalysisResult(
            analysis_id=f"mold_failed_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["Reconstructed STEP file contains no primary solid body."],
        )

    try:
        content = step_path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()

        res = _engine.analyze(
            shape=shape,
            mold_parameters=params,
            reconstruction_id=project_id,
            artifact_hash=sha256,
            source_filename=step_path.name,
            source_type="2D_RECONSTRUCTED_BREP",
        )

        out_json = pdir / "mold_analysis.json"
        out_json.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        return res
    finally:
        load_res.close()


# ---------------------------------------------------------------------------
# UC1 Standard STEP Project Mold Analysis Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/mold-analysis",
    response_model=MoldAnalysisResult,
    summary="Get or Compute Mold Analysis for Uploaded STEP Model",
)
def get_step_project_mold_analysis(
    project_id: str,
    direction: Optional[str] = Query(None, description="Optional opening direction label e.g. +Z, -Z, +Y"),
    min_draft: Optional[float] = Query(None, description="Optional minimum draft angle in degrees"),
) -> MoldAnalysisResult:
    """Executes identical geometric moldability analysis on an independently uploaded STEP CAD model."""
    try:
        meta = _project_svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    step_path = Path(meta.get("step_file", ""))
    if not step_path.exists():
        raise HTTPException(status_code=404, detail=f"STEP file for project '{project_id}' not found.")

    load_res = load_step(step_path)
    shape = load_res.primary_shape
    if not shape:
        load_res.close()
        return MoldAnalysisResult(
            analysis_id=f"mold_failed_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["STEP CAD model contains no primary solid body."],
        )

    try:
        sha256 = meta.get("sha256_hash") or hashlib.sha256(step_path.read_bytes()).hexdigest()

        params = MoldParameters()
        if min_draft is not None:
            params.minimum_draft_angle = min_draft
            params.user_configured_fields.append("minimum_draft_angle")
        if direction:
            dir_map = {
                "+z": [0.0, 0.0, 1.0], "-z": [0.0, 0.0, -1.0],
                "+y": [0.0, 1.0, 0.0], "-y": [0.0, -1.0, 0.0],
                "+x": [1.0, 0.0, 0.0], "-x": [-1.0, 0.0, 0.0],
            }
            if direction.lower() in dir_map:
                params.mold_opening_direction = dir_map[direction.lower()]
                params.direction_label = direction
                params.user_configured_fields.append("mold_opening_direction")

        res = _engine.analyze(
            shape=shape,
            mold_parameters=params,
            reconstruction_id=project_id,
            artifact_hash=sha256,
            source_filename=meta.get("filename", step_path.name),
            source_type="STEP_IMPORTED_BREP",
        )

        pdir = step_path.parent
        out_json = pdir / "mold_analysis.json"
        out_json.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        return res
    finally:
        load_res.close()


@router.post(
    "/projects/{project_id}/mold-analysis",
    response_model=MoldAnalysisResult,
    summary="Execute Configured Mold Analysis for Uploaded STEP Model",
)
def run_step_project_mold_analysis(
    project_id: str,
    params: MoldParameters,
) -> MoldAnalysisResult:
    """Executes geometric mold analysis with custom manufacturing parameters on uploaded STEP model."""
    try:
        meta = _project_svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    step_path = Path(meta.get("step_file", ""))
    if not step_path.exists():
        raise HTTPException(status_code=404, detail=f"STEP file for project '{project_id}' not found.")

    load_res = load_step(step_path)
    shape = load_res.primary_shape
    if not shape:
        load_res.close()
        return MoldAnalysisResult(
            analysis_id=f"mold_failed_{project_id[:8]}",
            reconstruction_id=project_id,
            status="VALIDATION_FAILED",
            is_valid_brep=False,
            overall_moldability="MOLD ANALYSIS UNAVAILABLE",
            errors=["STEP CAD model contains no primary solid body."],
        )

    try:
        sha256 = meta.get("sha256_hash") or hashlib.sha256(step_path.read_bytes()).hexdigest()

        res = _engine.analyze(
            shape=shape,
            mold_parameters=params,
            reconstruction_id=project_id,
            artifact_hash=sha256,
            source_filename=meta.get("filename", step_path.name),
            source_type="STEP_IMPORTED_BREP",
        )

        pdir = step_path.parent
        out_json = pdir / "mold_analysis.json"
        out_json.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        return res
    finally:
        load_res.close()
