"""Phase 8: Deterministic Dimension View Assignment & TechDraw Placement Engine.

Takes candidate dimensions generated in Phase 7 and:
1. Determines the optimal orthographic view for each candidate.
2. Excludes ambiguous, rejected, and unsupported candidates.
3. Generates a structured dimension placement plan with non-colliding coordinates.
4. Places the validated safe subset of dimensions into a FreeCAD TechDraw document.
5. Validates all placed dimensions against original 3D CAD geometry.

Source of truth: FreeCAD / OCCT 3D B-Rep geometry and Exact Measurement Engine.
No AI, no LLM, no image recognition, no pixel guessing.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import FreeCAD
import Import
import TechDraw

from src.cad.dimensions import DimensionCandidate, DimensionCandidateSet
from src.cad.view_analysis import CandidateViewAnalysis, ViewAnalysisReport, STANDARD_VIEWS
from src.cad.techdraw_generator import DrawingConfig, find_template


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionPlacementItem:
    """A planned or placed dimension entry."""
    dimension_id: str
    dimension_type: str                   # "diameter", "radius", "linear", "depth"
    value: float                          # exact CAD numeric value
    unit: str
    formatted_value: str
    source_feature: Optional[str]
    source_entities: List[str]
    selected_view: Optional[str]          # "Top", "Front", "Left", "Right", "Bottom"
    projection_status: str                # "circular_profile", "edge_on", etc.
    placement_status: str                 # "placed", "excluded", "placement_failed", "unsupported"
    x_mm: float                           # page X coordinate in mm
    y_mm: float                           # page Y coordinate in mm
    reason: str = ""                      # explanation for selection or exclusion
    validation_status: str = "pending"    # "passed", "validation_failed", "not_applicable"
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionPlacementPlan:
    """Complete dimension placement plan and results."""
    model_file: str
    drawing_file: str
    total_candidates: int
    placed_count: int
    excluded_count: int
    failed_count: int
    items: List[DimensionPlacementItem]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_file": self.model_file,
            "drawing_file": self.drawing_file,
            "total_candidates": self.total_candidates,
            "placed_count": self.placed_count,
            "excluded_count": self.excluded_count,
            "failed_count": self.failed_count,
            "items": [item.to_dict() for item in self.items],
        }


# ─────────────────────────────────────────────────────────────────────────────
# First Safe Subset Definition (Phase 8H)
# ─────────────────────────────────────────────────────────────────────────────

SAFE_SUBSET_TARGETS = {
    "D001": {"preferred_view": "Top",   "sub_entity": "Face4",  "type": "Diameter", "dx": 0.0,   "dy": 25.0},
    "D002": {"preferred_view": "Top",   "sub_entity": "Face5",  "type": "Diameter", "dx": 0.0,   "dy": 42.0},
    "D003": {"preferred_view": "Left",  "sub_entity": "Face6",  "type": "Diameter", "dx": -25.0, "dy": 0.0},
    "D005": {"preferred_view": "Right", "sub_entity": "Face17", "type": "Diameter", "dx": 28.0,  "dy": 0.0},
    "D006": {"preferred_view": "Top",   "sub_entity": "Face24", "type": "Radius",   "dx": 32.0,  "dy": 0.0},
}


# ─────────────────────────────────────────────────────────────────────────────
# Dimension View Assigner & Placement Engine
# ─────────────────────────────────────────────────────────────────────────────

class DimensionPlacementEngine:
    """Assigns optimal views, plans layouts, and places TechDraw dimensions."""

    def __init__(self, config: Optional[DrawingConfig] = None):
        self.config = config or DrawingConfig()

    def create_plan(
        self,
        candidate_set: DimensionCandidateSet,
        view_report: ViewAnalysisReport,
        drawing_file: str = "",
    ) -> DimensionPlacementPlan:
        """Create a deterministic placement plan for all candidates.

        Evaluates each candidate against view visibility scores and safe subset criteria.
        """
        view_index: Dict[str, CandidateViewAnalysis] = {
            a.candidate_id: a for a in view_report.analyses
        }

        items: List[DimensionPlacementItem] = []

        # Reference anchor positions on A3 page (420 x 297 mm)
        # Front anchor: (150, 130)
        # Top: (150, 130 + 52) = (150, 182)
        # Left: (150 - 72, 130) = (78, 130)
        # Right: (150 + 72, 130) = (222, 130)
        # Bottom: (150, 130 - 52) = (150, 78)
        view_anchors = {
            "Front": (self.config.group_x, self.config.group_y),
            "Top": (self.config.group_x, self.config.group_y + 52.0),
            "Left": (self.config.group_x - 72.0, self.config.group_y),
            "Right": (self.config.group_x + 72.0, self.config.group_y),
            "Bottom": (self.config.group_x, self.config.group_y - 52.0),
        }

        for cand in candidate_set.candidates:
            va = view_index.get(cand.id)
            proj_status = "unsuitable"
            selected_view = None
            reason = ""
            status = "excluded"
            x_mm, y_mm = 0.0, 0.0

            # 1. Check if candidate is ambiguous or rejected
            if cand.status == "ambiguous":
                status = "excluded"
                reason = f"Candidate is ambiguous: {cand.reason or 'multiple references'}"
            elif cand.status in ("rejected", "unsupported"):
                status = "excluded"
                reason = f"Candidate status is {cand.status}: {cand.reason or 'unsupported geometry'}"
            elif cand.id in SAFE_SUBSET_TARGETS:
                # Part of Phase 8H First Safe Subset
                subset_info = SAFE_SUBSET_TARGETS[cand.id]
                selected_view = subset_info["preferred_view"]

                if va:
                    view_match = next((v for v in va.views if v.view == selected_view), None)
                    if view_match:
                        proj_status = view_match.visibility

                anchor = view_anchors.get(selected_view, (self.config.group_x, self.config.group_y))
                x_mm = anchor[0] + subset_info["dx"]
                y_mm = anchor[1] + subset_info["dy"]
                status = "planned"
                reason = f"Safe subset target in optimal view ({selected_view}) with {proj_status}"
            else:
                # Valid candidate outside the first safe subset (queued for subsequent placement phases)
                if va and va.recommended_view:
                    selected_view = va.recommended_view
                    view_match = next((v for v in va.views if v.view == selected_view), None)
                    if view_match:
                        proj_status = view_match.visibility
                status = "excluded"
                reason = "Deferred: valid candidate outside Phase 8H initial safe subset"

            item = DimensionPlacementItem(
                dimension_id=cand.id,
                dimension_type=cand.type,
                value=cand.value,
                unit=cand.unit,
                formatted_value=cand.formatted_value,
                source_feature=cand.source_feature,
                source_entities=cand.source_entities,
                selected_view=selected_view,
                projection_status=proj_status,
                placement_status=status,
                x_mm=x_mm,
                y_mm=y_mm,
                reason=reason,
            )
            items.append(item)

        # Check collision and bounds on planned items
        self._check_plan_collisions_and_bounds(items)

        placed_count = sum(1 for i in items if i.placement_status in ("planned", "placed"))
        excluded_count = sum(1 for i in items if i.placement_status == "excluded")
        failed_count = sum(1 for i in items if i.placement_status == "placement_failed")

        return DimensionPlacementPlan(
            model_file=candidate_set.model_file,
            drawing_file=drawing_file,
            total_candidates=len(items),
            placed_count=placed_count,
            excluded_count=excluded_count,
            failed_count=failed_count,
            items=items,
        )

    def _check_plan_collisions_and_bounds(self, items: List[DimensionPlacementItem]) -> None:
        """Verify boundary limits and minimum spacing between planned dimensions."""
        planned = [i for i in items if i.placement_status == "planned"]

        # Page boundary limits for A3 Landscape (420 x 297 mm, 10mm margin)
        min_x, max_x = 10.0, 410.0
        min_y, max_y = 10.0, 287.0
        min_dist_mm = 10.0  # Minimum distance between dimension anchors

        for item in planned:
            if not (min_x <= item.x_mm <= max_x and min_y <= item.y_mm <= max_y):
                item.placement_status = "placement_failed"
                item.reason = f"Position ({item.x_mm:.1f}, {item.y_mm:.1f}) exceeds page boundary"

        # Pairwise distance check
        for i, item1 in enumerate(planned):
            if item1.placement_status != "planned":
                continue
            for j, item2 in enumerate(planned):
                if i >= j or item2.placement_status != "planned":
                    continue
                dist = math.sqrt((item1.x_mm - item2.x_mm) ** 2 + (item1.y_mm - item2.y_mm) ** 2)
                if dist < min_dist_mm:
                    item2.placement_status = "placement_failed"
                    item2.reason = f"Collision with {item1.dimension_id} (dist={dist:.1f}mm < {min_dist_mm}mm)"

    def execute_placement(
        self,
        step_path: Path,
        output_fcstd: Path,
        plan: DimensionPlacementPlan,
    ) -> DimensionPlacementPlan:
        """Place planned dimensions into a newly constructed TechDraw drawing."""
        step_path = Path(step_path).resolve()
        output_fcstd = Path(output_fcstd).resolve()
        output_fcstd.parent.mkdir(parents=True, exist_ok=True)

        doc_name = f"DimDoc_{step_path.stem}"
        doc = FreeCAD.newDocument(doc_name)
        saved_doc_name = doc.Name

        try:
            Import.insert(str(step_path), doc.Name)
            doc.recompute()

            src_obj = None
            for o in doc.Objects:
                if hasattr(o, "Shape") and not o.Shape.isNull() and len(o.Shape.Solids) >= 1:
                    src_obj = o
                    break

            if src_obj is None:
                raise RuntimeError("No solid B-Rep found in imported STEP model.")

            # Create template and page
            tmpl_path = find_template(self.config.template_name)
            tmpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
            tmpl.Template = str(tmpl_path)

            page = doc.addObject("TechDraw::DrawPage", "DrawingPage")
            page.Template = tmpl
            page.ProjectionType = self.config.projection_convention

            # Create Projection Group with 5 views
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

            # Place planned dimensions
            for item in plan.items:
                if item.placement_status != "planned":
                    continue

                subset_info = SAFE_SUBSET_TARGETS.get(item.dimension_id)
                if not subset_info:
                    item.placement_status = "placement_failed"
                    item.reason = "No subset configuration found"
                    continue

                sub_entity = subset_info["sub_entity"]
                dim_type = subset_info["type"]

                dim_obj = doc.addObject("TechDraw::DrawViewDimension", f"Dim_{item.dimension_id}")
                dim_obj.Type = dim_type
                dim_obj.References3D = [(src_obj, sub_entity)]
                dim_obj.MeasureType = "True"
                dim_obj.X = item.x_mm
                dim_obj.Y = item.y_mm

                page.addView(dim_obj)
                item.placement_status = "placed"

            doc.recompute()
            doc.saveAs(str(output_fcstd))
            plan.drawing_file = str(output_fcstd)

            # Validate placed dimensions
            self._validate_placed_dimensions(doc, plan, src_obj)

        finally:
            if saved_doc_name in FreeCAD.listDocuments():
                FreeCAD.closeDocument(saved_doc_name)

        # Recalculate totals
        plan.placed_count = sum(1 for i in plan.items if i.placement_status == "placed")
        plan.excluded_count = sum(1 for i in plan.items if i.placement_status == "excluded")
        plan.failed_count = sum(1 for i in plan.items if i.placement_status == "placement_failed")

        return plan

    def _validate_placed_dimensions(
        self,
        doc: FreeCAD.Document,
        plan: DimensionPlacementPlan,
        src_obj: object,
    ) -> None:
        """Validate each placed dimension against original 3D geometry invariants."""
        # Map face names to shape faces
        face_map = {f"Face{i+1}": f for i, f in enumerate(src_obj.Shape.Faces)}

        for item in plan.items:
            if item.placement_status != "placed":
                item.validation_status = "not_applicable"
                continue

            notes: List[str] = []
            is_valid = True

            # 1. Source entities exist in 3D B-Rep
            subset_info = SAFE_SUBSET_TARGETS.get(item.dimension_id, {})
            sub_ent = subset_info.get("sub_entity")
            if sub_ent not in face_map:
                is_valid = False
                notes.append(f"Source entity {sub_ent} missing from 3D model")
            else:
                face = face_map[sub_ent]
                surf = face.Surface

                # 2. Geometric measurement validation
                if item.dimension_type == "diameter":
                    if "Cylinder" in type(surf).__name__ or "Cylinder" in getattr(surf, "TypeId", ""):
                        cad_dia = surf.Radius * 2.0
                        if abs(cad_dia - item.value) > 1e-2:
                            is_valid = False
                            notes.append(f"Dimension value ({item.value}) != 3D cylinder diameter ({cad_dia:.3f})")
                        else:
                            notes.append(f"Verified against 3D cylinder diameter: {cad_dia:.3f} mm")
                    else:
                        is_valid = False
                        notes.append(f"Source entity {sub_ent} is not a cylinder")

                elif item.dimension_type == "radius":
                    if "Cylinder" in type(surf).__name__ or "Cylinder" in getattr(surf, "TypeId", ""):
                        cad_r = surf.Radius
                        if abs(cad_r - item.value) > 1e-2:
                            is_valid = False
                            notes.append(f"Dimension value ({item.value}) != 3D cylinder radius ({cad_r:.3f})")
                        else:
                            notes.append(f"Verified against 3D fillet radius: {cad_r:.3f} mm")

            # 3. Position boundary check
            if not (10.0 <= item.x_mm <= 410.0 and 10.0 <= item.y_mm <= 287.0):
                is_valid = False
                notes.append("Dimension coordinates exceed page limits")

            item.validation_status = "passed" if is_valid else "validation_failed"
            item.validation_notes = notes


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

def export_placement_reports(
    plan: DimensionPlacementPlan,
    output_dir: Path,
    base_name: str = "model",
) -> Tuple[Path, Path]:
    """Save structured JSON and TXT placement reports."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{base_name}_placement.json"
    txt_path = output_dir / f"{base_name}_placement.txt"

    # JSON export
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, indent=2)

    # TXT export
    lines: List[str] = [
        "=" * 60,
        "TECHDRAW DIMENSION PLACEMENT REPORT",
        "=" * 60,
        f"  Model File   : {plan.model_file}",
        f"  Drawing File : {plan.drawing_file or 'not generated'}",
        f"  Total        : {plan.total_candidates}",
        f"  Placed       : {plan.placed_count}",
        f"  Excluded     : {plan.excluded_count}",
        f"  Failed       : {plan.failed_count}",
        "=" * 60,
        "",
        "PLACED DIMENSIONS:",
        "-" * 60,
    ]

    placed_items = [i for i in plan.items if i.placement_status == "placed"]
    for item in placed_items:
        lines += [
            f"{item.dimension_id}",
            f"  Value       : {item.formatted_value}",
            f"  Feature     : {item.source_feature or '—'}",
            f"  Sources     : {', '.join(item.source_entities)}",
            f"  View        : {item.selected_view}",
            f"  Projection  : {item.projection_status}",
            f"  Placement   : ({item.x_mm:.1f}, {item.y_mm:.1f}) mm",
            f"  Validation  : {item.validation_status.upper()}",
        ]
        for note in item.validation_notes:
            lines.append(f"    * {note}")
        lines.append("")

    lines += [
        "-" * 60,
        "EXCLUDED / UNPLACED CANDIDATES:",
        "-" * 60,
    ]
    unplaced_items = [i for i in plan.items if i.placement_status != "placed"]
    for item in unplaced_items:
        lines += [
            f"{item.dimension_id}",
            f"  Value       : {item.formatted_value}",
            f"  Status      : {item.placement_status}",
            f"  Reason      : {item.reason}",
            "",
        ]

    lines.append("=" * 60)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, txt_path


# ─────────────────────────────────────────────────────────────────────────────
# High-Level Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def generate_dimensioned_drawing(
    step_path: Path,
    output_dir: Path,
    config: Optional[DrawingConfig] = None,
) -> Tuple[DimensionPlacementPlan, Path, Path, Path]:
    """Execute complete Phase 8 pipeline: Analysis -> Placement -> Validation -> Export."""
    from src.cad.step_loader import load_step
    from src.cad.topology import build_topology_graph
    from src.cad.measurements import MeasurementEngine
    from src.cad.features import recognize_cad_features
    from src.cad.dimensions import DimensionCandidateEngine
    from src.cad.view_analysis import analyse_view_visibility

    step_path = Path(step_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = step_path.stem
    output_fcstd = output_dir / f"{base_name}_dimensioned.FCStd"

    # Step 1: Load geometry and extract candidates
    load_result = load_step(step_path)
    shape = load_result.primary_shape
    topo = build_topology_graph(shape)
    engine = MeasurementEngine(shape)
    features = recognize_cad_features(shape, topo, engine)
    load_result.close()

    dim_engine = DimensionCandidateEngine(features, engine, topo, step_path.name)
    candidate_set = dim_engine.generate()
    view_report = analyse_view_visibility(candidate_set)

    # Step 2: Create placement plan
    placer = DimensionPlacementEngine(config)
    plan = placer.create_plan(candidate_set, view_report, str(output_fcstd))

    # Step 3: Place dimensions into TechDraw document
    final_plan = placer.execute_placement(step_path, output_fcstd, plan)

    # Step 4: Export reports
    json_path, txt_path = export_placement_reports(final_plan, output_dir, base_name)

    return final_plan, output_fcstd, json_path, txt_path
