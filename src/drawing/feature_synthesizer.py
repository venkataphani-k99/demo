"""Phase 18.1 — Evidence-Driven Engineering Feature Synthesizer.

Synthesizes physical features with explicit provenance, spatial entity integration,
computed confidence, and structured uncertainty representation.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from src.drawing.projection_aligner import ProjectionAligner
from src.drawing.schemas import (
    BoundingBox,
    CSGOperation,
    DimensionType,
    DrawingFeature,
    EntityType,
    ExtractedDimension,
    FeatureEvidenceRecord,
    FeatureGraph,
    FeatureParameter,
    FeatureType,
    GeometricEntity,
    KnowledgeState,
    ReconstructionBlueprint,
    ViewType,
)


def _bbox_center(b: Optional[BoundingBox]) -> Optional[Tuple[float, float]]:
    if not b:
        return None
    return ((b.x1 + b.x2) / 2.0, (b.y1 + b.y2) / 2.0)


def _spatial_distance(b1: Optional[BoundingBox], b2: Optional[BoundingBox]) -> float:
    c1 = _bbox_center(b1)
    c2 = _bbox_center(b2)
    if not c1 or not c2:
        return 99999.0
    return math.hypot(c1[0] - c2[0], c1[1] - c2[1])


class FeatureSynthesizer:
    """Evidence-driven synthesizer converting 2D annotations and entities into a traceable FeatureGraph."""

    def __init__(self) -> None:
        self.aligner = ProjectionAligner()

    def synthesize(
        self,
        dimensions: List[ExtractedDimension],
        views_map: Dict[str, ViewType],
        entities: Optional[List[GeometricEntity]] = None,
        claude_dims: Optional[List[ExtractedDimension]] = None,
        gemini_dims: Optional[List[ExtractedDimension]] = None,
    ) -> FeatureGraph:
        """Synthesizes an evidence-backed FeatureGraph.

        Parameters
        ----------
        dimensions : List[ExtractedDimension]
            Consensus or combined dimensions.
        views_map : Dict[str, ViewType]
            Mapping from view_id to ViewType.
        entities : Optional[List[GeometricEntity]]
            Detected entities from multimodal models.
        claude_dims : Optional[List[ExtractedDimension]]
            Original Claude dimensions for provenance/conflict checks.
        gemini_dims : Optional[List[ExtractedDimension]]
            Original Gemini dimensions for provenance/conflict checks.

        Returns
        -------
        FeatureGraph
            Traceable mechanical feature model and CSG reconstruction blueprint.
        """
        entities = entities or []
        claude_dims = claude_dims or []
        gemini_dims = gemini_dims or []

        # 1. Orthographic axis alignment & envelope computation
        cross_view = self.aligner.align(dimensions, views_map)
        envelope = cross_view.estimated_envelope_3d

        # 2. Match canonical dimension callouts with Claude / Gemini records
        c_map = {d.raw_text: d for d in claude_dims}
        g_map = {d.raw_text: d for d in gemini_dims}

        # Deduplicate dimensions by numeric value
        unique_dims: List[ExtractedDimension] = []
        seen_vals: Set[Optional[float]] = set()
        for d in dimensions:
            val_q = round(d.normalized_value, 2) if d.normalized_value is not None else None
            if val_q not in seen_vals:
                seen_vals.add(val_q)
                unique_dims.append(d)

        features: List[DrawingFeature] = []
        feat_idx = 1
        missing_params: List[str] = []
        ambiguous_feat_ids: List[str] = []

        # 3. Base Body Feature (from resolved envelope axes)
        base_params: List[FeatureParameter] = []
        base_views: Set[ViewType] = set()
        base_dim_ids: List[str] = []
        base_dim_texts: List[str] = []

        if envelope.get("width_x") is not None:
            base_params.append(FeatureParameter(param_name="width_x", value=envelope["width_x"], unit="mm"))
        else:
            missing_params.append("Part Width (X) envelope dimension unconfirmed")

        if envelope.get("depth_y") is not None:
            base_params.append(FeatureParameter(param_name="depth_y", value=envelope["depth_y"], unit="mm"))
        else:
            missing_params.append("Part Depth (Y) envelope dimension unconfirmed")

        if envelope.get("height_z") is not None:
            base_params.append(FeatureParameter(param_name="height_z", value=envelope["height_z"], unit="mm"))
        else:
            missing_params.append("Part Height (Z) envelope dimension unconfirmed (no vertical callout)")

        # Collect source views contributing to base envelope
        for d in unique_dims:
            if d.raw_text in cross_view.width_x_dimensions or d.raw_text in cross_view.depth_y_dimensions or d.raw_text in cross_view.height_z_dimensions:
                base_dim_ids.append(d.dimension_id)
                base_dim_texts.append(d.raw_text)
                vtype = views_map.get(d.view_id, ViewType.UNKNOWN) if d.view_id else ViewType.UNKNOWN
                if vtype != ViewType.UNKNOWN:
                    base_views.add(vtype)

        base_kstate = KnowledgeState.KNOWN if (len(base_params) == 3) else KnowledgeState.PARTIALLY_KNOWN
        base_conf = 0.90 if len(base_params) == 3 else 0.75

        features.append(DrawingFeature(
            feature_id=f"FEAT_{feat_idx:03d}",
            feature_type=FeatureType.BASE_BODY,
            name="Envelope Body Structure",
            knowledge_state=base_kstate,
            controlling_view_types=sorted(list(base_views), key=lambda v: v.value),
            parameters=base_params,
            evidence=f"Synthesized from confirmed orthographic dimensions: {', '.join(base_dim_texts)}.",
            evidence_record=FeatureEvidenceRecord(
                source_dimension_ids=base_dim_ids,
                source_dimension_texts=base_dim_texts,
                source_view_ids=[d.view_id for d in unique_dims if d.dimension_id in base_dim_ids and d.view_id],
                inference_rules=["Cross-view projection envelope resolution"],
            ),
            ambiguity_reasons=["Height (Z) unconfirmed due to lack of explicit vertical callout."] if envelope.get("height_z") is None else [],
            confidence=base_conf,
        ))
        feat_idx += 1

        # 4. Synthesize Individual Geometric Features (Cylinders, Fillets, Steps)
        for d in unique_dims:
            raw = d.raw_text
            val = d.normalized_value
            if val is None:
                continue

            # Find matching Claude & Gemini records for deep provenance
            c_rec = c_map.get(raw) or next((cd for cd in claude_dims if abs((cd.normalized_value or -99) - val) < 0.05), None)
            g_rec = g_map.get(raw) or next((gd for gd in gemini_dims if abs((gd.normalized_value or -99) - val) < 0.05), None)

            c_type = c_rec.dimension_type.value if c_rec else "absent"
            g_type = g_rec.dimension_type.value if g_rec else "absent"
            c_view = c_rec.view_id if c_rec else None
            g_view = g_rec.view_id if g_rec else None

            # Collect all views associated with this measurement
            feat_views: Set[ViewType] = set()
            for vid in (d.view_id, c_view, g_view):
                if vid and vid in views_map:
                    feat_views.add(views_map[vid])
            v_list = sorted(list(feat_views), key=lambda v: v.value)

            # Spatial entity matching: find entities in any associated view within 220px
            matched_entities = [
                e for e in entities
                if (e.view_id in (d.view_id, c_view, g_view))
                and _spatial_distance(d.bbox, e.bbox) < 220.0
            ]
            matched_ent_ids = list(dict.fromkeys([e.entity_id for e in matched_entities]))
            has_circle = any(e.entity_type == EntityType.CIRCLE for e in matched_entities)
            has_arc = any(e.entity_type == EntityType.ARC for e in matched_entities)
            has_center = any(e.entity_type == EntityType.CENTER_MARK for e in matched_entities)

            # Compute Evidence-Based Confidence & Knowledge State
            conf = 0.70
            rules: List[str] = ["Consensus agreed numeric value"]
            conflicts: List[str] = []
            kstate = KnowledgeState.KNOWN

            if c_type == g_type and c_type not in ("unknown", "absent"):
                conf += 0.10
                rules.append(f"Model semantic type agreement ({c_type})")
            elif c_type != g_type and c_type != "absent" and g_type != "absent":
                conf -= 0.15
                conflicts.append(f"Type conflict: Claude={c_type}, Gemini={g_type}")
                kstate = KnowledgeState.AMBIGUOUS

            if c_view == g_view and c_view is not None:
                conf += 0.10
                rules.append(f"Model view agreement ({c_view})")
            elif c_view != g_view and c_view is not None and g_view is not None:
                conf -= 0.20
                conflicts.append(f"View conflict: Claude={c_view}, Gemini={g_view}")
                kstate = KnowledgeState.AMBIGUOUS

            if matched_entities:
                bonus = min(0.10, len(matched_entities) * 0.05)
                conf += bonus
                rules.append(f"Corroborated by {len(matched_entities)} geometric entity callout(s)")

            conf = max(0.10, min(0.99, round(conf, 2)))

            # Feature Classification Logic
            vtype = views_map.get(d.view_id, ViewType.UNKNOWN) if d.view_id else ViewType.UNKNOWN
            v_list = [vtype] if vtype != ViewType.UNKNOWN else []

            # Check if diameter / radius / linear
            is_diameter = "diameter" in c_type or "diameter" in g_type or "ø" in raw.lower()
            is_radius = "radius" in c_type or "radius" in g_type or raw.upper().startswith("R")

            if is_diameter:
                if kstate == KnowledgeState.AMBIGUOUS:
                    ftype = FeatureType.CYLINDRICAL
                    fname = f"Ambiguous Cylindrical Callout ({raw})"
                    ambiguous_feat_ids.append(f"FEAT_{feat_idx:03d}")
                elif has_arc:
                    ftype = FeatureType.BOSS
                    fname = f"Cylindrical Boss/Arc Feature ({raw})"
                elif has_circle or has_center:
                    ftype = FeatureType.HOLE
                    fname = f"Through Hole ({raw})"
                else:
                    ftype = FeatureType.CYLINDRICAL
                    fname = f"Cylindrical Feature ({raw})"

                features.append(DrawingFeature(
                    feature_id=f"FEAT_{feat_idx:03d}",
                    feature_type=ftype,
                    name=fname,
                    knowledge_state=kstate,
                    controlling_view_types=v_list,
                    parameters=[FeatureParameter(param_name="diameter", value=val, unit=d.unit or "mm", source_dimension_id=d.dimension_id, source_dimension_text=raw, confidence=conf)],
                    bbox_union=d.bbox,
                    evidence=f"Cylindrical callout {raw} in view {vtype.value}. " + (f"Supported by entities: {', '.join(matched_ent_ids)}" if matched_ent_ids else "No explicit entity overlap."),
                    evidence_record=FeatureEvidenceRecord(
                        source_dimension_ids=[d.dimension_id],
                        source_dimension_texts=[raw],
                        source_entity_ids=matched_ent_ids,
                        source_view_ids=[d.view_id] if d.view_id else [],
                        claude_types=[c_type],
                        gemini_types=[g_type],
                        consensus_states=["agreed"],
                        inference_rules=rules,
                        conflicts=conflicts,
                    ),
                    ambiguity_reasons=conflicts,
                    confidence=conf,
                ))
                feat_idx += 1

            elif is_radius:
                features.append(DrawingFeature(
                    feature_id=f"FEAT_{feat_idx:03d}",
                    feature_type=FeatureType.FILLET,
                    name=f"Corner Blend Radius ({raw})",
                    knowledge_state=kstate,
                    controlling_view_types=v_list,
                    parameters=[FeatureParameter(param_name="radius", value=val, unit=d.unit or "mm", source_dimension_id=d.dimension_id, source_dimension_text=raw, confidence=conf)],
                    bbox_union=d.bbox,
                    evidence=f"Fillet/round callout {raw} located in view {vtype.value}.",
                    evidence_record=FeatureEvidenceRecord(
                        source_dimension_ids=[d.dimension_id],
                        source_dimension_texts=[raw],
                        source_entity_ids=matched_ent_ids,
                        source_view_ids=[d.view_id] if d.view_id else [],
                        claude_types=[c_type],
                        gemini_types=[g_type],
                        consensus_states=["agreed"],
                        inference_rules=rules,
                        conflicts=conflicts,
                    ),
                    ambiguity_reasons=conflicts,
                    confidence=conf,
                ))
                feat_idx += 1

            else:
                # Linear dimension not part of the primary envelope max
                # Represent as a Linear Step / Cutout Feature without inventing a 0.0 height slot
                features.append(DrawingFeature(
                    feature_id=f"FEAT_{feat_idx:03d}",
                    feature_type=FeatureType.LINEAR_STEP,
                    name=f"Linear Feature Span ({raw})",
                    knowledge_state=kstate if kstate != KnowledgeState.KNOWN else KnowledgeState.PARTIALLY_KNOWN,
                    controlling_view_types=v_list,
                    parameters=[FeatureParameter(param_name="span_length", value=val, unit=d.unit or "mm", source_dimension_id=d.dimension_id, source_dimension_text=raw, confidence=conf)],
                    bbox_union=d.bbox,
                    evidence=f"Linear callout {raw} in view {vtype.value}.",
                    evidence_record=FeatureEvidenceRecord(
                        source_dimension_ids=[d.dimension_id],
                        source_dimension_texts=[raw],
                        source_entity_ids=matched_ent_ids,
                        source_view_ids=[d.view_id] if d.view_id else [],
                        claude_types=[c_type],
                        gemini_types=[g_type],
                        consensus_states=["agreed"],
                        inference_rules=rules,
                        conflicts=conflicts,
                    ),
                    ambiguity_reasons=conflicts,
                    confidence=conf,
                ))
                feat_idx += 1

        # 5. Build CSG Operations (only for KNOWN / PARTIALLY_KNOWN features)
        csg_ops: List[CSGOperation] = []
        op_step = 1

        # Step 1: Base Extrusion
        max_w = envelope.get("width_x") or 0.0
        max_d = envelope.get("depth_y") or 0.0
        max_h = envelope.get("height_z") or 0.0

        if max_w > 0 and max_d > 0:
            h_str = f"{max_h} mm" if max_h > 0 else "unconstrained height"
            csg_ops.append(CSGOperation(
                step=op_step,
                operation_type="base_pad_extrusion",
                target_feature_id="FEAT_001",
                description=f"Extrude base envelope profile ({max_w} x {max_d} mm) along Z to {h_str}.",
                parameters={"width_x": max_w, "depth_y": max_d, "height_z": max_h if max_h > 0 else None},
            ))
            op_step += 1

        # Step 2: Cylindrical hole / bore cutouts (skip ambiguous features)
        for feat in features:
            if feat.feature_type in (FeatureType.HOLE, FeatureType.BOSS, FeatureType.CYLINDRICAL):
                if feat.knowledge_state in (KnowledgeState.AMBIGUOUS, KnowledgeState.UNRESOLVED):
                    continue
                dia = next((p.value for p in feat.parameters if p.param_name == "diameter"), 0.0)
                if dia > 0:
                    op_type = "hole_drill_cutout" if feat.feature_type == FeatureType.HOLE else "cylindrical_boss_feature"
                    csg_ops.append(CSGOperation(
                        step=op_step,
                        operation_type=op_type,
                        target_feature_id=feat.feature_id,
                        description=f"Create cylindrical feature Ø{dia} mm at confirmed view reference location.",
                        parameters={"diameter": dia, "views": [v.value for v in feat.controlling_view_types]},
                    ))
                    op_step += 1

        # Step 3: Fillet Blends
        for feat in features:
            if feat.feature_type == FeatureType.FILLET:
                rad = next((p.value for p in feat.parameters if p.param_name == "radius"), 0.0)
                if rad > 0:
                    csg_ops.append(CSGOperation(
                        step=op_step,
                        operation_type="fillet_edge_blend",
                        target_feature_id=feat.feature_id,
                        description=f"Apply edge fillet blend radius R{rad} mm on transition edges.",
                        parameters={"radius": rad},
                    ))
                    op_step += 1

        known_count = sum(1 for f in features if f.knowledge_state == KnowledgeState.KNOWN)
        completeness = round(known_count / len(features), 2) if features else 0.0
        c_status = "fully_constrained" if (len(missing_params) == 0 and len(ambiguous_feat_ids) == 0) else "partially_constrained"

        blueprint = ReconstructionBlueprint(
            envelope_3d=envelope,
            ordered_operations=csg_ops,
            constraint_status=c_status,
            completeness_score=completeness,
            ambiguous_features=ambiguous_feat_ids,
            missing_parameters=missing_params,
        )

        return FeatureGraph(
            features=features,
            cross_view_alignment=cross_view,
            blueprint=blueprint,
            synthesis_timestamp=datetime.now(timezone.utc).isoformat(),
        )
