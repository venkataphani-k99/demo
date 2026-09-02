"""Engineering Intelligence Pipeline: Full orchestration from CAD -> AI Reasoning -> Gatekeeper -> TechDraw."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import FreeCAD
import Import
import TechDraw

from src.intelligence.decision_model import DrawingDecisionSet, EngineeringDecision, VisionReviewResult
from src.intelligence.providers import EngineeringReasoningProvider, get_reasoning_provider
from src.intelligence.tools import CADToolRegistry
from src.intelligence.vision_reviewer import DrawingVisionReviewer, MockDrawingVisionReviewer
from src.cad.complete_dimensioning import COMPLETE_PLACEMENT_SPECS
from src.cad.techdraw_generator import DrawingConfig, find_template


class DeterministicValidationGatekeeper:
    """Strictly validates all AI reasoning decisions against immutable CAD geometry."""

    TOL_NUMERIC = 1e-3
    VALID_DECISIONS = {"include", "exclude", "defer", "ambiguous", "requires_human_review"}
    VALID_VIEWS = {"Front", "Top", "Left", "Right", "Bottom"}
    VALID_PRIORITIES = {"PRIMARY", "SECONDARY", "OPTIONAL", "AMBIGUOUS"}

    def validate(
        self,
        decisions: List[EngineeringDecision],
        tools: CADToolRegistry,
    ) -> List[EngineeringDecision]:
        """Validate every decision against CAD ground truth across 9 strict engineering checks."""
        cand_map = {c["id"]: c for c in tools.get_dimension_candidates()}
        feature_ids = {f["feature_id"] for f in tools.get_features()}
        face_map = tools.engine.face_map

        for d in decisions:
            notes: List[str] = []
            is_valid = True

            # Check 1: Unsupported decision type
            if d.decision not in self.VALID_DECISIONS:
                is_valid = False
                notes.append(f"Unsupported decision type '{d.decision}' (allowed: {sorted(self.VALID_DECISIONS)})")

            # Check 2: Missing or empty reason
            if not d.reason or not d.reason.strip():
                is_valid = False
                notes.append("Missing engineering rationale/reason")

            # Check 3: Candidate ID must exist in deterministic candidates
            if d.dimension_id not in cand_map:
                is_valid = False
                notes.append(f"Dimension ID '{d.dimension_id}' not found in candidate dataset (hallucination rejected)")
            else:
                cand = cand_map[d.dimension_id]

                # Check 4: Exact numeric value check: AI must not alter numeric value
                if abs(d.exact_cad_value - cand["value"]) > self.TOL_NUMERIC:
                    is_valid = False
                    notes.append(f"Value mismatch: decision={d.exact_cad_value} vs OCCT CAD={cand['value']} (hallucinated number rejected)")
                else:
                    notes.append("Exact OCCT numeric value confirmed")

                # Check 5: Unit correctness check
                cand_unit = cand.get("unit", "mm")
                if d.unit != cand_unit:
                    is_valid = False
                    notes.append(f"Unit mismatch: decision='{d.unit}' vs OCCT CAD='{cand_unit}'")

                # Check 6: Source entity check
                for eid in d.source_entities:
                    if eid not in face_map:
                        is_valid = False
                        notes.append(f"Source entity '{eid}' missing from 3D model")

                # Check 7: Feature ID check (if specified)
                if d.source_feature and d.source_feature not in feature_ids:
                    is_valid = False
                    notes.append(f"Source feature ID '{d.source_feature}' not found in recognized CAD features")

                # Check 8: Selected view validity for included dimensions
                if d.decision == "include":
                    if not d.selected_view or d.selected_view not in self.VALID_VIEWS:
                        is_valid = False
                        notes.append(f"Invalid selected view '{d.selected_view}' for included dimension")

            # Check 9: Priority validity
            if d.priority not in self.VALID_PRIORITIES:
                is_valid = False
                notes.append(f"Invalid priority '{d.priority}'")

            # Human review triggers
            if d.decision == "ambiguous" or d.confidence < 0.85:
                d.requires_review = True
                if d.confidence < 0.85 and "confidence_below_threshold" not in d.review_flags:
                    d.review_flags.append("confidence_below_threshold")

            d.validation_status = "passed" if is_valid else "validation_failed"
            d.validation_notes = notes

        return decisions


class EngineeringIntelligencePipeline:
    """Orchestrates CAD extraction, AI reasoning, Gatekeeper validation, and drawing generation."""

    def __init__(
        self,
        provider: Optional[EngineeringReasoningProvider] = None,
        vision_reviewer: Optional[DrawingVisionReviewer] = None,
        config: Optional[DrawingConfig] = None,
    ):
        self.provider = provider or get_reasoning_provider("mock")
        self.vision_reviewer = vision_reviewer or MockDrawingVisionReviewer()
        self.gatekeeper = DeterministicValidationGatekeeper()
        self.config = config or DrawingConfig()

    def run(
        self,
        step_path: Path,
        output_dir: Path,
    ) -> Tuple[DrawingDecisionSet, Path, Path, Path]:
        """Execute full Phase 10 engineering drawing intelligence workflow."""
        step_path = Path(step_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = step_path.stem
        context_json_path = output_dir / f"{base_name}_engineering_context.json"
        decisions_json_path = output_dir / f"{base_name}_engineering_decisions.json"
        drawing_fcstd_path = output_dir / f"{base_name}_intelligent_drawing.FCStd"

        # 1. Initialize CAD Tool Registry & extract deterministic context
        tools = CADToolRegistry(step_path)
        context = {
            "model_summary": tools.get_model_summary(),
            "features": tools.get_features(),
            "dimension_candidates": tools.get_dimension_candidates(),
            "dependencies": tools.get_dimension_dependencies(),
            "datums": tools.get_datums(),
            "coverage": tools.get_dimension_coverage(),
        }

        # Export engineering context JSON
        context_json_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

        # 2. Invoke Engineering Reasoning Provider
        raw_decisions = self.provider.evaluate_candidates(tools, context)

        # 3. Pass decisions through Deterministic Validation Gatekeeper
        validated_decisions = self.gatekeeper.validate(raw_decisions, tools)

        # 4. Place approved dimensions on TechDraw Drawing
        self._generate_intelligent_techdraw(step_path, drawing_fcstd_path, validated_decisions)

        # 5. Multimodal Drawing Vision Review
        vision_result = self.vision_reviewer.review_drawing(
            svg_or_image_path=output_dir / f"{base_name}_drawing.svg",
            engineering_context=context,
            decisions=validated_decisions,
        )

        # 6. Build Decision Set Summary
        included = [d for d in validated_decisions if d.decision == "include"]
        excluded = [d for d in validated_decisions if d.decision == "exclude"]
        deferred = [d for d in validated_decisions if d.decision == "defer"]
        ambiguous = [d for d in validated_decisions if d.decision == "ambiguous"]
        review_req = [d for d in validated_decisions if d.requires_review]

        decision_set = DrawingDecisionSet(
            model_file=step_path.name,
            drawing_file=str(drawing_fcstd_path),
            total_candidates=len(validated_decisions),
            included_count=len(included),
            excluded_count=len(excluded),
            deferred_count=len(deferred),
            ambiguous_count=len(ambiguous),
            review_required_count=len(review_req),
            provider_name=self.provider.provider_name,
            decisions=validated_decisions,
            vision_review=vision_result,
            feature_coverages=tools.get_dimension_coverage(),
            potential_datums=tools.get_datums(),
        )

        # Export decisions JSON
        decisions_json_path.write_text(
            json.dumps(decision_set.model_dump(), indent=2),
            encoding="utf-8",
        )

        return decision_set, context_json_path, decisions_json_path, drawing_fcstd_path

    def _generate_intelligent_techdraw(
        self,
        step_path: Path,
        output_fcstd: Path,
        decisions: List[EngineeringDecision],
    ) -> None:
        """Generate TechDraw drawing with AI-approved, gatekeeper-validated dimensions."""
        doc_name = f"IntelligentDoc_{step_path.stem}"
        doc = FreeCAD.newDocument(doc_name)
        saved_name = doc.Name

        try:
            Import.insert(str(step_path), doc.Name)
            doc.recompute()

            src_obj = next(o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull() and len(o.Shape.Solids) >= 1)

            tmpl_path = find_template(self.config.template_name)
            tmpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
            tmpl.Template = str(tmpl_path)

            page = doc.addObject("TechDraw::DrawPage", "DrawingPage")
            page.Template = tmpl
            page.ProjectionType = self.config.projection_convention

            pg = doc.addObject("TechDraw::DrawProjGroup", "ProjGroup")
            pg.Source = [src_obj]
            pg.ScaleType = "Automatic"
            pg.ProjectionType = self.config.projection_convention
            pg.spacingX = self.config.spacing_x
            pg.spacingY = self.config.spacing_y

            front = pg.addProjection("Front")
            pg.addProjection("Top")
            pg.addProjection("Left")
            pg.addProjection("Right")
            pg.addProjection("Bottom")
            pg.Anchor = front
            pg.X = self.config.group_x
            pg.Y = self.config.group_y

            page.addView(pg)
            doc.recompute()

            view_anchors = {
                "Front": (self.config.group_x, self.config.group_y),
                "Top": (self.config.group_x, self.config.group_y + 52.0),
                "Left": (self.config.group_x - 72.0, self.config.group_y),
                "Right": (self.config.group_x + 72.0, self.config.group_y),
                "Bottom": (self.config.group_x, self.config.group_y - 52.0),
            }

            for d in decisions:
                if d.decision != "include" or d.validation_status != "passed":
                    continue

                spec = COMPLETE_PLACEMENT_SPECS.get(d.dimension_id, {})
                sub_ent = spec.get("sub_entity", "Face1")
                dim_type = spec.get("type", "Distance")
                v_name = d.selected_view or "Front"
                anchor = view_anchors.get(v_name, (self.config.group_x, self.config.group_y))

                dim_obj = doc.addObject("TechDraw::DrawViewDimension", f"Dim_{d.dimension_id}")
                dim_obj.Type = dim_type
                dim_obj.References3D = [(src_obj, sub_ent)]
                dim_obj.MeasureType = "True"
                dim_obj.X = anchor[0] + spec.get("dx", 0.0)
                dim_obj.Y = anchor[1] + spec.get("dy", 0.0)

                page.addView(dim_obj)

            doc.recompute()
            doc.saveAs(str(output_fcstd))

        finally:
            if saved_name in FreeCAD.listDocuments():
                FreeCAD.closeDocument(saved_name)
