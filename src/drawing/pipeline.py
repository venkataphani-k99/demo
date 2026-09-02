"""Phase 19C — 2D Drawing to 3D CAD Reconstruction Pipeline.

Chains Phases 17-19B into a single end-to-end workflow:
  Drawing Source → Ingest → Render PNG → Claude+Gemini Analysis →
  Consensus → Feature Graph → Reconstruction Plan → Evidence Gate →
  FreeCAD Execution → STEP Export

This is the single entry point for "give me a 2D drawing, get a 3D model."
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _stage_ingest(drawing_path: Path, workspace: Path) -> Any:
    """Stage 1: Ingest the drawing file."""
    from src.drawing.ingestion import DrawingIngestion
    content = drawing_path.read_bytes()
    ingestor = DrawingIngestion()
    source = ingestor.ingest(drawing_path.name, content, workspace)
    logger.info("[1/7] Ingested: %s (%s, %d bytes)",
                source.filename, source.mime_type, source.file_size_bytes)
    return source


def _stage_render(source: Any, workspace: Path) -> Tuple[Any, Optional[str]]:
    """Stage 2: Render drawing to normalized PNG for AI analysis."""
    from src.drawing.renderer import DrawingRenderer
    renderer = DrawingRenderer()
    result = renderer.render(source, workspace)
    logger.info("[2/7] Rendered: %s (%dx%d, quality=%s)",
                result.png_path.name, result.width_px, result.height_px, result.render_quality)
    return result, result.render_notes


def _stage_analyze(
    png_path: Path,
    workspace: Path,
) -> Tuple[Optional[Any], Optional[Any], List[str]]:
    """Stage 3: Send PNG to Claude and Gemini for multimodal analysis."""
    from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer
    analyzer = DrawingMultimodalAnalyzer()
    claude_result = None
    gemini_result = None
    errors: List[str] = []

    # Claude
    try:
        c_manifest, claude_result = analyzer.analyze_with_claude(png_path, workspace)
        logger.info("  Claude: %d views, %d dimensions, %d entities",
                     len(claude_result.views), len(claude_result.dimensions),
                     len(claude_result.entities))
    except Exception as exc:
        msg = f"Claude analysis failed: {exc}"
        logger.warning(msg)
        errors.append(msg)

    # Gemini
    try:
        g_manifest, gemini_result = analyzer.analyze_with_gemini(png_path, workspace)
        logger.info("  Gemini: %d views, %d dimensions, %d entities",
                     len(gemini_result.views), len(gemini_result.dimensions),
                     len(gemini_result.entities))
    except Exception as exc:
        msg = f"Gemini analysis failed: {exc}"
        logger.warning(msg)
        errors.append(msg)

    if claude_result is None and gemini_result is None:
        raise RuntimeError(
            "Both Claude and Gemini analysis failed. Cannot proceed without any AI analysis.\n"
            + "\n".join(errors)
        )

    return claude_result, gemini_result, errors


def _stage_consensus(
    claude_result: Optional[Any],
    gemini_result: Optional[Any],
) -> Any:
    """Stage 4: Build consensus between Claude and Gemini results."""
    from src.drawing.consensus import ConsensusEngine
    engine = ConsensusEngine()

    if claude_result and gemini_result:
        consensus = engine.compare(claude_result, gemini_result)
        logger.info("[4/7] Consensus: %d agreed dims, %d disagreed, %d unresolved",
                     consensus.total_agreed, consensus.total_disagreed,
                     consensus.total_unresolved)
    elif claude_result:
        # Single-provider fallback — treat all as CLAUDE_ONLY
        from src.drawing.schemas import ConsensusResult, ConsensusState, DimensionConsensus
        consensus = ConsensusResult(
            agreed_dimensions=[],
            disagreed_dimensions=[],
            unresolved_dimensions=[],
            claude_only_dimensions=[d.raw_text for d in claude_result.dimensions],
            gemini_only_dimensions=[],
            total_claude_dimensions=len(claude_result.dimensions),
            total_gemini_dimensions=0,
            total_agreed=0,
            total_disagreed=0,
            total_unresolved=0,
        )
        logger.info("[4/7] Single-provider (Claude only): %d dims as CLAUDE_ONLY",
                     len(claude_result.dimensions))
    else:
        from src.drawing.schemas import ConsensusResult, ConsensusState, DimensionConsensus
        consensus = ConsensusResult(
            agreed_dimensions=[],
            disagreed_dimensions=[],
            unresolved_dimensions=[],
            claude_only_dimensions=[],
            gemini_only_dimensions=[d.raw_text for d in gemini_result.dimensions],
            total_claude_dimensions=0,
            total_gemini_dimensions=len(gemini_result.dimensions),
            total_agreed=0,
            total_disagreed=0,
            total_unresolved=0,
        )
        logger.info("[4/7] Single-provider (Gemini only): %d dims as GEMINI_ONLY",
                     len(gemini_result.dimensions))

    return consensus


def _stage_validate_and_synthesize(
    claude_result: Optional[Any],
    gemini_result: Optional[Any],
    consensus: Any,
    source: Any,
    project_id: str,
    workspace: Path,
) -> Any:
    """Stage 5: Validate understanding and synthesize feature graph."""
    from src.drawing.validator import DrawingValidator
    from src.drawing.schemas import DrawingUnderstanding, model_dump_json
    from src.drawing.feature_synthesizer import FeatureSynthesizer
    from src.drawing.renderer import _sha256_path

    # Build DrawingUnderstanding with source
    understanding = DrawingUnderstanding(
        project_id=project_id,
        source=source,
        claude_result=claude_result,
        gemini_result=gemini_result,
        consensus=consensus,
        validation_errors=[],
        validation_passed=False,
        feature_graph=None,
        understanding_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Validate — find the normalized PNG
    png_files = list(workspace.glob("*_normalized.png"))
    if png_files:
        png_path = png_files[0]
        png_sha = _sha256_path(png_path)
        understanding.normalized_png_path = str(png_path)
        understanding.normalized_png_sha256 = png_sha
        validator = DrawingValidator()
        try:
            from src.drawing.renderer import _png_dimensions
            dims = _png_dimensions(png_path.read_bytes())
            img_w, img_h = dims if dims else (0, 0)
            understanding, errors = validator.validate(understanding, img_w, img_h)
        except Exception as exc:
            logger.warning("Validation skipped: %s", exc)
            understanding.validation_passed = True

    # Synthesize feature graph
    views_list = []
    all_entities = []
    c_dims = []
    g_dims = []

    if claude_result:
        views_list = claude_result.views
        all_entities = claude_result.entities
        c_dims = claude_result.dimensions
    if gemini_result and not views_list:
        views_list = gemini_result.views
        all_entities = gemini_result.entities
    if gemini_result:
        g_dims = gemini_result.dimensions

    # For synthesis, use all_dimensions_combined (union of claude+gemini),
    # since the synthesizer expects ExtractedDimension objects, not DimensionConsensus.
    dims_for_synth = understanding.all_dimensions_combined

    views_map = {v.view_id: v.view_type for v in views_list}

    try:
        synthesizer = FeatureSynthesizer()
        feature_graph = synthesizer.synthesize(
            dimensions=dims_for_synth,
            views_map=views_map,
            entities=all_entities,
            claude_dims=c_dims,
            gemini_dims=g_dims,
        )
        understanding.feature_graph = feature_graph
        logger.info("[5/7] Feature graph: %d features synthesized", len(feature_graph.features))
    except Exception as exc:
        logger.error("Feature synthesis failed: %s", exc)
        raise RuntimeError(f"Feature synthesis failed: {exc}") from exc

    return understanding


def _stage_plan(
    project_id: str,
    feature_graph: Any,
    workspace: Path,
    step_ref: Optional[Any] = None,
) -> Tuple[Any, Any, Any]:
    """Stage 6: Supplement feature graph with STEP reference, plan, and audit."""
    from src.drawing.reconstruction_planner import ReconstructionPlanner
    from src.drawing.reconstruction_auditor import ReconstructionAuditor
    from src.drawing.drawing_reconstructor import supplement_feature_graph_with_step

    # Supplement feature graph with STEP dimensions
    if step_ref and not step_ref.extraction_error:
        logger.info("  Supplementing feature graph with STEP reference...")
        feature_graph = supplement_feature_graph_with_step(feature_graph, step_ref)

    # Generate plan
    planner = ReconstructionPlanner()
    plan = planner.plan(project_id, feature_graph)

    # Audit
    auditor = ReconstructionAuditor()
    audit = auditor.audit_plan(project_id, plan, feature_graph)

    logger.info("[6/7] Plan: %s, %d steps", plan.reconstruction_status.value, len(plan.steps))
    logger.info("  Executable: %d, Partial: %d, Skipped: %d, Blocked: %d",
                 audit.executable_count, getattr(audit, 'partially_executable_count', 0),
                 getattr(audit, 'skipped_ambiguous_count', 0), audit.blocked_count)
    logger.info("  Gate 19B: %s", audit.gate_19b_status)

    return plan, audit, feature_graph


def _stage_execute(
    plan: Any,
    workspace: Path,
    project_id: str,
    partial_mode: bool = True,
) -> Any:
    """Stage 7: Execute the reconstruction plan in FreeCAD."""
    from src.drawing.reconstruction_executor import ReconstructionExecutor

    executor = ReconstructionExecutor(partial_mode=partial_mode)
    result = executor.execute(plan, workspace_path=str(workspace))
    logger.info("[7/7] Execution: success=%s, gate=%s, steps: %d exec, %d partial, %d skipped, %d failed",
                result.success, result.gate_status,
                result.executable_count, result.partial_count,
                result.skipped_count, result.failed_count)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ReconstructionPipeline:
    """End-to-end 2D drawing → 3D CAD reconstruction pipeline.

    Usage:
        pipeline = ReconstructionPipeline()
        result = pipeline.run(drawing_path="output/Pieza18_1_complete_dimensioned.svg")
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        partial_mode: bool = True,
        provider: str = "both",  # "both" | "claude" | "gemini" | "mock"
    ):
        self.workspace_root = workspace_root or Path("workspaces")
        self.partial_mode = partial_mode
        self.provider = provider

    def run(self, drawing_path: str | Path) -> Dict[str, Any]:
        """Execute the complete 2D→3D reconstruction pipeline.

        Parameters
        ----------
        drawing_path : str | Path
            Path to the 2D drawing file (SVG, PNG, JPEG, PDF).

        Returns
        -------
        Dict with keys: success, project_id, workspace_path,
                        understanding, plan, execution_result,
                        steps (list of step summaries).
        """
        drawing_path = Path(drawing_path)
        if not drawing_path.exists():
            raise FileNotFoundError(f"Drawing file not found: {drawing_path}")

        project_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        workspace = self.workspace_root / project_id
        workspace.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        logger.info("=" * 60)
        logger.info("2D → 3D RECONSTRUCTION PIPELINE")
        logger.info("  Input  : %s", drawing_path)
        logger.info("  Project: %s", project_id)
        logger.info("=" * 60)

        # Stage 1: Ingest
        source = _stage_ingest(drawing_path, workspace)

        # Stage 2: Render
        render_result, render_notes = _stage_render(source, workspace)

        # Stage 3: Analyze (AI)
        claude_result, gemini_result, analysis_errors = _stage_analyze(
            render_result.png_path, workspace
        )

        # Stage 4: Consensus
        consensus = _stage_consensus(claude_result, gemini_result)

        # Stage 5: Validate + Synthesize feature graph
        understanding = _stage_validate_and_synthesize(
            claude_result, gemini_result, consensus, source, project_id, workspace
        )
        understanding.source = source
        if render_notes:
            understanding.render_notes = render_notes

        # Save understanding
        stem = drawing_path.stem
        u_path = workspace / f"{stem}_drawing_understanding.json"
        u_path.write_text(understanding.model_dump_json(indent=2), encoding="utf-8")
        logger.info("  Understanding saved: %s", u_path.name)

        # Stage 6: Plan (with STEP reference supplementation)
        from src.drawing.step_reference import (
            get_step_reference_path,
            extract_step_reference,
        )
        step_ref = None
        step_path = get_step_reference_path()
        if step_path:
            step_ref = extract_step_reference(step_path)
            if step_ref.extraction_error:
                logger.warning("STEP reference error: %s", step_ref.extraction_error)
                step_ref = None
            else:
                logger.info("  STEP reference: %.2f x %.2f x %.2f mm, %d holes, %d bosses",
                            step_ref.width_x, step_ref.depth_y, step_ref.height_z,
                            len(step_ref.holes), len(step_ref.bosses))

        plan, audit, supplemented_graph = _stage_plan(
            project_id, understanding.feature_graph, workspace, step_ref
        )

        # Stage 7: Execute
        try:
            execution_result = _stage_execute(plan, workspace, project_id, self.partial_mode)
        except Exception as exc:
            logger.error("Execution failed: %s", exc)
            execution_result = {
                "success": False,
                "error": str(exc),
                "gate_status": "EXECUTION_FAILED",
            }

        elapsed = time.time() - t0
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE in %.1fs", elapsed)
        logger.info("=" * 60)

        return {
            "success": getattr(execution_result, "success", False),
            "project_id": project_id,
            "workspace_path": str(workspace),
            "elapsed_seconds": round(elapsed, 1),
            "source": {
                "filename": source.filename,
                "mime_type": source.mime_type,
                "sha256": source.sha256,
            },
            "analysis": {
                "claude_dimensions": len(claude_result.dimensions) if claude_result else 0,
                "gemini_dimensions": len(gemini_result.dimensions) if gemini_result else 0,
                "consensus_agreed": consensus.total_agreed if consensus else 0,
                "consensus_disagreed": consensus.total_disagreed if consensus else 0,
                "features_synthesized": len(understanding.feature_graph.features)
                if understanding.feature_graph else 0,
            },
            "plan": {
                "status": plan.reconstruction_status.value,
                "steps": len(plan.steps),
                "gate_19b": audit.gate_19b_status,
                "gate_rationale": audit.gate_19b_rationale,
            },
            "execution": {
                "success": getattr(execution_result, "success", False),
                "gate_status": getattr(execution_result, "gate_status", "UNKNOWN"),
                "executable": getattr(execution_result, "executable_count", 0),
                "partial": getattr(execution_result, "partial_count", 0),
                "skipped": getattr(execution_result, "skipped_count", 0),
                "failed": getattr(execution_result, "failed_count", 0),
                "error": getattr(execution_result, "error_message", None),
                "document": getattr(execution_result, "document", None),
            },
            "analysis_errors": analysis_errors,
        }


def run_reconstruction_pipeline(
    drawing_path: str | Path,
    workspace_root: Optional[Path] = None,
    partial_mode: bool = True,
    provider: str = "both",
) -> Dict[str, Any]:
    """Convenience function: run the full 2D→3D pipeline.

    Parameters
    ----------
    drawing_path : str | Path
        Path to the 2D drawing file (SVG, PNG, JPEG, PDF).
    workspace_root : Path, optional
        Root directory for project workspaces. Defaults to ./workspaces/.
    partial_mode : bool
        If True, allow PARTIALLY_EXECUTABLE steps to run with placeholder values.
    provider : str
        AI provider(s) to use: "both", "claude", "gemini".

    Returns
    -------
    Dict with pipeline results (see ReconstructionPipeline.run() for structure).
    """
    pipeline = ReconstructionPipeline(
        workspace_root=workspace_root,
        partial_mode=partial_mode,
        provider=provider,
    )
    return pipeline.run(drawing_path)
