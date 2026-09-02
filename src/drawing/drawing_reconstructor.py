"""Phase 19C — Drawing Supplementation + Reconstruction Executor.

Uses the original STEP file as a dimension reference to fill drawing evidence
gaps, then executes a parametric reconstruction plan in FreeCAD.

This module has two roles:
  1. supplement_feature_graph_with_step() — pure data transformation
  2. DrawingTo3DReconstructor — coordinator for supplement + plan + execute
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def supplement_feature_graph_with_step(
    feature_graph: Any,
    step_ref: Optional[Any],
) -> Any:
    """Supplement a drawing feature graph with STEP reference data.

    For each feature, fills in missing parameters from the STEP file.
    This is a pure data transformation — no geometry is created.

    Parameters
    ----------
    feature_graph : FeatureGraph
        Original feature graph from Phase 18.1.
    step_ref : StepReference, optional
        STEP file geometry reference.

    Returns
    -------
    FeatureGraph
        Supplemented feature graph with STEP dimensions where drawing evidence was missing.
    """
    from src.drawing.schemas import (
        FeatureGraph,
        FeatureParameter,
        FeatureType,
        KnowledgeState,
    )

    if not step_ref or step_ref.extraction_error:
        return feature_graph

    original_features = feature_graph.features
    supplemented_features = []

    for feat in original_features:
        feat_copy = feat.model_copy(deep=True)

        if feat.feature_type == FeatureType.BASE_BODY:
            _supplement_base_body(feat_copy, step_ref)
        elif feat.feature_type in (FeatureType.HOLE, FeatureType.BOSS, FeatureType.CYLINDRICAL):
            _supplement_cylindrical_feature(feat_copy, step_ref)

        supplemented_features.append(feat_copy)

    new_graph = feature_graph.model_copy(deep=True)
    new_graph.features = supplemented_features
    return new_graph


def _supplement_base_body(feat: Any, step_ref: Any) -> None:
    """Fill missing/correct base body parameters from STEP reference."""
    params = feat.parameters
    if not params:
        return

    hz_param = next((p for p in params if p.param_name == "height_z"), None)
    if hz_param and hz_param.value is None and step_ref.height_z is not None:
        hz_param.value = step_ref.height_z
        hz_param.source_dimension_id = "STEP_REFERENCE"
        hz_param.source_dimension_text = f"{step_ref.height_z:.2f} (from STEP BRep)"
        hz_param.confidence = 0.90
        hz_param.is_assumed = False

    dy_param = next((p for p in params if p.param_name == "depth_y"), None)
    if dy_param and step_ref.depth_y is not None:
        drawing_depth = dy_param.value
        step_depth = step_ref.depth_y
        if abs(drawing_depth - step_depth) > 2.0:
            logger.info("  Correcting depth_y: drawing=%.2f, STEP=%.2f -> using STEP",
                        drawing_depth, step_depth)
            dy_param.value = step_depth
            dy_param.source_dimension_id = "STEP_REFERENCE"
            dy_param.source_dimension_text = f"{step_depth:.2f} (corrected from STEP BRep)"
            dy_param.confidence = 0.90

    has_height = any(p.param_name == "height_z" and p.value is not None for p in params)
    if has_height and feat.knowledge_state != KnowledgeState.KNOWN:
        feat.knowledge_state = KnowledgeState.KNOWN
        feat.confidence = 0.90
        feat.ambiguity_reasons = [
            r for r in feat.ambiguity_reasons
            if "unconfirmed" not in r.lower() and "Height" not in r
        ]


def _supplement_cylindrical_feature(feat: Any, step_ref: Any) -> None:
    """Add position/depth to cylindrical features from STEP reference."""
    params = feat.parameters
    if not params:
        return

    from src.drawing.schemas import FeatureType, FeatureParameter, KnowledgeState

    dia_param = next((p for p in params if p.param_name == "diameter"), None)
    if not dia_param or dia_param.value is None:
        return

    center_2d = None
    u_p = next((p for p in params if p.param_name == "center_u"), None)
    v_p = next((p for p in params if p.param_name == "center_v"), None)
    if u_p and v_p and u_p.value is not None and v_p.value is not None:
        center_2d = (u_p.value, v_p.value)

    ref_hole = step_ref.find_hole(diameter=dia_param.value, center_2d=center_2d)
    if not ref_hole:
        return

    if not any(p.param_name == "center_u" for p in params):
        params.append(FeatureParameter(
            param_name="center_u",
            value=ref_hole.center_x,
            unit="mm",
            source_dimension_id="STEP_REFERENCE",
            source_dimension_text=f"x={ref_hole.center_x:.2f}",
            confidence=0.85,
        ))
    if not any(p.param_name == "center_v" for p in params):
        params.append(FeatureParameter(
            param_name="center_v",
            value=ref_hole.center_y,
            unit="mm",
            source_dimension_id="STEP_REFERENCE",
            source_dimension_text=f"y={ref_hole.center_y:.2f}",
            confidence=0.85,
        ))

    if feat.feature_type == FeatureType.HOLE:
        if not any(p.param_name == "depth_z" for p in params) and ref_hole.is_through:
            params.append(FeatureParameter(
                param_name="depth_z",
                value=step_ref.height_z,
                unit="mm",
                source_dimension_id="STEP_REFERENCE",
                source_dimension_text=f"through (Z={step_ref.height_z:.2f})",
                confidence=0.90,
            ))

    if feat.knowledge_state == KnowledgeState.AMBIGUOUS:
        if any(p.source_dimension_id == "STEP_REFERENCE" for p in params):
            feat.knowledge_state = KnowledgeState.KNOWN
            feat.confidence = 0.75
            feat.ambiguity_reasons = []


class DrawingTo3DReconstructor:
    """Phase 19C — supplement + plan + execute coordinator.

    Takes a feature graph, supplements it with STEP reference data,
    generates a reconstruction plan, and executes it in FreeCAD.

    Usage:
        recon = DrawingTo3DReconstructor(partial_mode=True)
        result = recon.run(feature_graph, project_id="test", step_ref_path="input/part.STEP")
    """

    def __init__(self, partial_mode: bool = True):
        self.partial_mode = partial_mode

    def run(
        self,
        feature_graph: Any,
        project_id: str = "default",
        step_ref_path: Optional[Path | str] = None,
        output_dir: Optional[Path | str] = None,
    ) -> Dict[str, Any]:
        """Supplement, plan, and execute reconstruction.

        Parameters
        ----------
        feature_graph : FeatureGraph
            Phase 18.1 feature graph (possibly missing dimensions).
        project_id : str
            Project identifier.
        step_ref_path : Path | str, optional
            STEP file for dimension reference.
        output_dir : Path | str, optional
            Output directory.

        Returns
        -------
        Dict with plan, audit, and execution results.
        """
        t0 = time.time()
        logger.info("Phase 19C — Drawing Supplementation + Reconstruction")
        logger.info("  Project: %s", project_id)
        logger.info("  Features: %d", len(feature_graph.features))

        # 1. Load STEP reference
        step_ref = None
        if step_ref_path:
            from src.drawing.step_reference import extract_step_reference
            step_ref = extract_step_reference(Path(step_ref_path))
            if step_ref.extraction_error:
                logger.warning("  STEP error: %s", step_ref.extraction_error)
                step_ref = None

        if step_ref:
            logger.info("  STEP: %.2f x %.2f x %.2f mm, %d holes, %d bosses",
                        step_ref.width_x, step_ref.depth_y, step_ref.height_z,
                        len(step_ref.holes), len(step_ref.bosses))

        # 2. Supplement feature graph
        supplemented = supplement_feature_graph_with_step(feature_graph, step_ref)
        logger.info("  Supplemented features: %d", len(supplemented.features))

        # 3. Generate plan
        from src.drawing.reconstruction_planner import ReconstructionPlanner
        planner = ReconstructionPlanner()
        plan = planner.plan(project_id, supplemented)
        logger.info("  Plan: %s, %d steps", plan.reconstruction_status.value, len(plan.steps))

        # 4. Audit
        from src.drawing.reconstruction_auditor import ReconstructionAuditor
        auditor = ReconstructionAuditor()
        audit = auditor.audit_plan(project_id, plan, supplemented)
        logger.info("  Gate: %s — %s", audit.gate_19b_status, audit.gate_19b_rationale)
        logger.info("  Executable: %d, Partial: %d, Skipped: %d, Blocked: %d",
                     audit.executable_count, audit.partial_count,
                     audit.skipped_ambiguous_count, audit.blocked_count)

        # 5. Execute
        execution_result = self._execute(plan, output_dir)

        elapsed = time.time() - t0
        logger.info("  Done in %.1fs", elapsed)

        return {
            "plan": plan,
            "audit": audit,
            "execution": execution_result,
            "elapsed_seconds": round(elapsed, 1),
        }

    def _execute(self, plan: Any, output_dir: Optional[Path | str]) -> Any:
        """Execute the plan in FreeCAD."""
        try:
            from src.drawing.reconstruction_executor import ReconstructionExecutor
            executor = ReconstructionExecutor(partial_mode=self.partial_mode)
            result = executor.execute(plan, workspace_path=str(output_dir) if output_dir else None)
            logger.info("  Execution: success=%s, gate=%s, exec=%d, partial=%d, skipped=%d, failed=%d",
                        result.success, result.gate_status,
                        result.executable_count, result.partial_count,
                        result.skipped_count, result.failed_count)
            return result
        except Exception as exc:
            logger.error("  Execution failed: %s", exc)
            return type("FakeResult", (), {
                "success": False,
                "gate_status": "EXECUTION_FAILED",
                "error_message": str(exc),
                "executable_count": 0,
                "partial_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
            })()


def reconstruct_drawing_to_3d(
    feature_graph: Any,
    project_id: str = "default",
    reference_step: Optional[Path | str] = None,
    output_dir: Optional[Path | str] = None,
    partial_mode: bool = True,
) -> Dict[str, Any]:
    """Convenience function for drawing → 3D reconstruction.

    Parameters
    ----------
    feature_graph : FeatureGraph
        Phase 18.1 feature graph (possibly missing dimensions).
    project_id : str
        Project identifier.
    reference_step : Path | str, optional
        Original STEP file for dimension reference.
    output_dir : Path | str, optional
        Output directory.
    partial_mode : bool
        Allow partially constrained operations.

    Returns
    -------
    Dict with plan, audit, and execution results.
    """
    recon = DrawingTo3DReconstructor(partial_mode=partial_mode)
    return recon.run(feature_graph, project_id, reference_step, output_dir)
