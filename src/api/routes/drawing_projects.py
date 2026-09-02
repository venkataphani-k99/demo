"""Phase 17 — FastAPI routes for UC2 Drawing Project ingestion and analysis."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from src.api.services.drawing_project_service import DrawingProjectService
from src.drawing.consensus import ConsensusEngine
from src.drawing.ingestion import ALLOWED_EXTENSIONS, DrawingIngestion
from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer
from src.drawing.renderer import DrawingRenderer
from src.drawing.schemas import DrawingUnderstanding
from src.drawing.validator import DrawingValidator
from src.cad.freecad_env import load_env_file as _load_env

# Ensure .env API keys are loaded into this process
_load_env()


router = APIRouter(prefix="/drawing-projects", tags=["Drawing Projects (UC2)"])
_svc = DrawingProjectService()


# ---------------------------------------------------------------------------
# GET /drawing-projects — List all drawing projects
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List all UC2 Drawing Projects",
)
def list_drawing_projects() -> list[Dict[str, Any]]:
    """Returns a list of all drawing projects in descending chronological order."""
    return _svc.list_projects()


# ---------------------------------------------------------------------------
# POST /drawing-projects — Upload drawing and create project
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload 2D Engineering Drawing and Create UC2 Project",
)
async def upload_drawing(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Accept a PDF, PNG, JPEG, or SVG engineering drawing.
    Creates an isolated UC2 workspace and returns project metadata.
    Does NOT run analysis — call /analyze separately.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file format '{ext}'. "
                f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        meta = _svc.create_project(file.filename, content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {exc}")

    return {
        "project_id": meta["project_id"],
        "filename": meta["filename"],
        "status": meta["status"],
        "created_at": meta["created_at"],
        "file_size_bytes": len(content),
    }


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id} — Project status
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}",
    summary="Get Drawing Project Status",
)
def get_drawing_project(project_id: str) -> Dict[str, Any]:
    """Returns current status, metadata, and available artifacts for a UC2 drawing project."""
    try:
        meta = _svc.get_project_metadata(project_id)
        return meta
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /drawing-projects/{id}/analyze — Full ingestion + AI analysis pipeline
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/analyze",
    summary="Run UC2 Drawing Analysis (Ingest → Render → Claude + Gemini → Consensus → Validate)",
)
def analyze_drawing_project(project_id: str) -> Dict[str, Any]:
    """
    Runs the full UC2 pipeline:
    1. Ingest source drawing → immutable copy + metadata
    2. Render to normalized PNG
    3. Send PNG image to Claude (with image_attached=True validation)
    4. Send PNG image to Gemini (with image_attached=True validation)
    5. Build deterministic consensus
    6. Validate structural correctness of AI output
    7. Save DrawingUnderstanding JSON artifact
    """
    try:
        meta = _svc.get_project_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Drawing project '{project_id}' not found.")

    raw_upload_path = Path(meta.get("raw_upload_path", ""))
    if not raw_upload_path.exists():
        raise HTTPException(status_code=422, detail="Source drawing file not found in workspace.")

    pdir = _svc.get_project_dir(project_id)
    filename = meta["filename"]
    content = raw_upload_path.read_bytes()

    try:
        _svc.update_status(project_id, "analyzing")

        # Step 1: Ingest
        ingestion = DrawingIngestion()
        source = ingestion.ingest(filename, content, pdir)

        # Step 2: Render
        renderer = DrawingRenderer()
        try:
            render_result = renderer.render(source, pdir)
        except Exception as exc:
            _svc.update_status(project_id, "error", f"Rendering failed: {exc}")
            raise HTTPException(
                status_code=422,
                detail=f"Drawing rendering failed: {exc}",
            )

        # Initialize understanding shell
        understanding = DrawingUnderstanding(
            project_id=project_id,
            source=source,
            normalized_png_path=str(render_result.png_path),
            normalized_png_sha256=render_result.sha256,
            render_quality=render_result.render_quality,
            render_notes=render_result.render_notes,
            understanding_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Step 3: Claude analysis
        analyzer = DrawingMultimodalAnalyzer()
        claude_error: str | None = None
        gemini_error: str | None = None

        try:
            c_manifest, c_result = analyzer.analyze_with_claude(render_result.png_path, pdir)
            understanding.claude_manifest = c_manifest
            understanding.claude_result = c_result
        except Exception as exc:
            claude_error = str(exc)
            from src.drawing.schemas import ModelResult
            understanding.claude_result = ModelResult(
                provider="claude",
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                error=claude_error,
                analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Step 4: Gemini analysis
        try:
            g_manifest, g_result = analyzer.analyze_with_gemini(render_result.png_path, pdir)
            understanding.gemini_manifest = g_manifest
            understanding.gemini_result = g_result
        except Exception as exc:
            gemini_error = str(exc)
            from src.drawing.schemas import ModelResult
            understanding.gemini_result = ModelResult(
                provider="gemini",
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                error=gemini_error,
                analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Step 5: Consensus (only if both providers succeeded)
        if (
            understanding.claude_result
            and not understanding.claude_result.error
            and understanding.gemini_result
            and not understanding.gemini_result.error
        ):
            engine = ConsensusEngine()
            understanding.consensus = engine.compare(
                understanding.claude_result, understanding.gemini_result
            )

        # Step 6: Validation
        validator = DrawingValidator()
        understanding, errors = validator.validate(
            understanding,
            render_result.width_px,
            render_result.height_px,
        )

        # Step 7: Phase 18.1 Evidence-Driven Feature Synthesis & 3D Blueprint
        try:
            from src.drawing.feature_synthesizer import FeatureSynthesizer
            views_list = (understanding.claude_result.views if understanding.claude_result else []) or (understanding.gemini_result.views if understanding.gemini_result else [])
            views_map = {v.view_id: v.view_type for v in views_list}
            dims_for_synth = understanding.all_dimensions_combined
            all_entities = (understanding.claude_result.entities if understanding.claude_result else []) + (understanding.gemini_result.entities if understanding.gemini_result else [])
            c_dims = understanding.claude_result.dimensions if understanding.claude_result else []
            g_dims = understanding.gemini_result.dimensions if understanding.gemini_result else []
            if dims_for_synth:
                synthesizer = FeatureSynthesizer()
                understanding.feature_graph = synthesizer.synthesize(
                    dims_for_synth,
                    views_map,
                    entities=all_entities,
                    claude_dims=c_dims,
                    gemini_dims=g_dims,
                )
        except Exception as synth_exc:
            # Non-blocking: synthesis issue should not cancel saved understanding
            pass

        # Step 8: Save
        json_path = _svc.save_understanding(project_id, understanding)

        # Step 9: Phase 19B Automatic 3D Mesh & Solid Generation
        try:
            from src.drawing.cad_reconstructor import CADReconstructor
            CADReconstructor().reconstruct_mesh(project_id, understanding=understanding)
        except Exception:
            pass

        return {
            "project_id": project_id,
            "status": "analyzed",
            "render_quality": render_result.render_quality,
            "render_notes": render_result.render_notes,
            "claude_views": len(understanding.claude_result.views) if understanding.claude_result else 0,
            "claude_dimensions": len(understanding.claude_result.dimensions) if understanding.claude_result else 0,
            "gemini_views": len(understanding.gemini_result.views) if understanding.gemini_result else 0,
            "gemini_dimensions": len(understanding.gemini_result.dimensions) if understanding.gemini_result else 0,
            "consensus_agreed": understanding.consensus.total_agreed if understanding.consensus else 0,
            "consensus_unresolved": understanding.consensus.total_unresolved if understanding.consensus else 0,
            "features_synthesized": len(understanding.feature_graph.features) if understanding.feature_graph else 0,
            "validation_passed": understanding.validation_passed,
            "validation_errors": len(errors),
            "claude_error": claude_error,
            "gemini_error": gemini_error,
            "artifact_path": str(json_path),
        }

    except HTTPException:
        raise
    except Exception as exc:
        _svc.update_status(project_id, "error", str(exc))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/understanding — Full understanding JSON
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/understanding",
    summary="Get Full Drawing Understanding",
)
def get_understanding(project_id: str) -> Dict[str, Any]:
    """Returns the complete DrawingUnderstanding for a project."""
    try:
        u = _svc.get_understanding(project_id)
        return u.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/feature-graph — Synthesized Feature Graph
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/feature-graph",
    summary="Get Synthesized Feature Graph",
)
def get_feature_graph(project_id: str) -> Dict[str, Any]:
    """Returns the recognized mechanical features, cross-view alignment, and constraints."""
    try:
        u = _svc.get_understanding(project_id)
        if not u.feature_graph:
            # On-the-fly synthesis fallback
            from src.drawing.feature_synthesizer import FeatureSynthesizer
            views_list = (u.claude_result.views if u.claude_result else []) or (u.gemini_result.views if u.gemini_result else [])
            views_map = {v.view_id: v.view_type for v in views_list}
            dims = u.all_dimensions_combined
            all_entities = (u.claude_result.entities if u.claude_result else []) + (u.gemini_result.entities if u.gemini_result else [])
            c_dims = u.claude_result.dimensions if u.claude_result else []
            g_dims = u.gemini_result.dimensions if u.gemini_result else []
            if dims:
                u.feature_graph = FeatureSynthesizer().synthesize(
                    dims,
                    views_map,
                    entities=all_entities,
                    claude_dims=c_dims,
                    gemini_dims=g_dims,
                )
                _svc.save_understanding(project_id, u)
        if u.feature_graph:
            return u.feature_graph.model_dump()
        return {"features": [], "cross_view_alignment": None, "blueprint": None}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/blueprint — 3D CSG Reconstruction Blueprint
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/blueprint",
    summary="Get Reconstruction Blueprint Recipe",
)
def get_blueprint(project_id: str) -> Dict[str, Any]:
    """Returns the 3D bounding box envelope and sequential CSG modeling recipe."""
    try:
        u = _svc.get_understanding(project_id)
        if u.feature_graph and u.feature_graph.blueprint:
            return u.feature_graph.blueprint.model_dump()
        return {"envelope_3d": {}, "ordered_operations": [], "constraint_status": "under_constrained"}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/reconstruction-plan — Phase 19A Reconstruction Blueprint
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/reconstruction-plan",
    summary="Get Phase 19A Parametric Reconstruction Plan",
)
def get_reconstruction_plan(project_id: str) -> Dict[str, Any]:
    """Returns the ordered parametric CAD DAG, parameter provenance, and status."""
    try:
        plan = _svc.get_reconstruction_plan(project_id)
        return plan.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/artifacts/{artifact_id} — Download artifact
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/artifacts/{artifact_id}",
    summary="Download UC2 Drawing Project Artifact",
)
def download_artifact(project_id: str, artifact_id: str) -> FileResponse:
    """Stream a downloadable artifact: normalized PNG, understanding JSON, or request manifests."""
    try:
        art_path = _svc.get_artifact_path(project_id, artifact_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found.")

    media_map = {
        ".png": "image/png",
        ".json": "application/json",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".svg": "image/svg+xml",
    }
    media_type = media_map.get(art_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(art_path),
        filename=art_path.name,
        media_type=media_type,
    )


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/mesh — Exact 3D B-Rep Mesh for Three.js
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/mesh",
    summary="Get 3D Reconstructed Mesh and Wireframe Geometry for Three.js Viewport",
)
def get_drawing_project_mesh(project_id: str, force_rebuild: bool = False) -> Dict[str, Any]:
    """Returns 3D triangulated mesh, edge wireframes, and per-face mappings extracted from reconstructed solid."""
    try:
        from src.drawing.cad_reconstructor import CADReconstructor
        return CADReconstructor().reconstruct_mesh(project_id, force_rebuild=force_rebuild)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"3D mesh generation failed: {exc}")


# ---------------------------------------------------------------------------
# POST /drawing-projects/{id}/gemini-reconstruct — Gemini 2D-to-3D CAD Engine
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/gemini-reconstruct",
    summary="Execute Gemini-Assisted 2D-to-3D CAD Reconstruction",
)
def gemini_reconstruct(project_id: str) -> Dict[str, Any]:
    """
    Invokes Gemini Vision CAD Brain to interpret drawing, generate a structured
    CAD reconstruction plan, execute it with controlled FreeCAD primitives, and export STEP + Mesh.
    """
    try:
        return _svc.gemini_reconstruct_cad(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini CAD reconstruction failed: {exc}")


# ---------------------------------------------------------------------------
# POST /drawing-projects/{id}/execute-plan — Execute Custom CAD Plan
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/execute-plan",
    summary="Execute a Structured CAD Reconstruction Plan via Controlled Tools",
)
def execute_cad_plan(project_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts a validated CADReconstructionPlan JSON and deterministically executes
    each step via FreeCAD / OpenCASCADE without running arbitrary Python code.
    """
    try:
        return _svc.execute_custom_cad_plan(project_id, plan)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CAD plan execution failed: {exc}")


# ---------------------------------------------------------------------------
# GET /drawing-projects/{id}/reconstruction-plan — Get CAD Plan JSON
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/reconstruction-plan",
    summary="Retrieve Active CAD Reconstruction Plan",
)
def get_reconstruction_plan(project_id: str) -> Dict[str, Any]:
    """Returns the JSON CAD reconstruction plan for this drawing project."""
    try:
        plan_path = _svc.get_artifact_path(project_id, "gemini_cad_plan")
        import json
        return json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            plan_path = _svc.get_artifact_path(project_id, "reconstruction_plan")
            import json
            return json.loads(plan_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="No reconstruction plan found for this project.")



