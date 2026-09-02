"""Phase 22 — Engineering Evidence Package Builder.

Transforms deterministic OCCT B-Rep audit results and Engineering Intelligence datasets
into a structured, compact JSON package suitable for evidence-constrained AI reasoning.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.cad.engineering_intelligence_engine import EngineeringIntelligenceReport


def build_evidence_package(report: Any) -> Dict[str, Any]:
    """Construct a clean, structured Engineering Evidence Package from CAD/OCCT intelligence."""
    if isinstance(report, dict):
        model_name = report.get("model_name", "UNKNOWN_MODEL.STEP")
        audit = report.get("audit_summary", {})
        env = audit.get("assembly_envelope_mm", [0.0, 0.0, 0.0])
        feature_graph = report.get("feature_graph", [])
        classified_dimensions = report.get("classified_dimensions", [])
        view_recs = report.get("view_recommendations", {})
        sec_recs = report.get("section_recommendations", {})
        missing_info = report.get("missing_information", [])
        ambiguities = report.get("ambiguities_detected", [])

        return {
            "metadata": {
                "model_name": model_name,
                "pipeline": "CAD_INTELLIGENCE_PHASE_22",
                "kernel": "OpenCASCADE_BRep_Ground_Truth",
            },
            "solid_geometry": {
                "is_brep_valid": True,
                "unique_solids_count": audit.get("unique_solids_count", 1),
                "raw_solids_count": audit.get("total_raw_solids", 1),
                "unique_faces_count": audit.get("unique_faces_count", 0),
                "unique_edges_count": audit.get("unique_edges_count", 0),
                "envelope_mm": {
                    "width_x": round(env[0], 3) if len(env) > 0 else 0.0,
                    "depth_y": round(env[1], 3) if len(env) > 1 else 0.0,
                    "height_z": round(env[2], 3) if len(env) > 2 else 0.0,
                },
                "volume_cm3": round(audit.get("total_volume_cm3", 0.0), 2),
                "surface_area_cm2": round(audit.get("total_surface_area_cm2", 0.0), 2),
                "surface_type_distribution": audit.get("surface_types", {}),
            },
            "ranked_features": [
                {
                    "feature_id": f.get("feature_id"),
                    "geometric_type": f.get("geometric_type"),
                    "source_faces": f.get("source_faces", []),
                    "source_edges": f.get("source_edges", []),
                    "measured_dimensions": f.get("measured_dimensions", {}),
                    "relevance_category": f.get("relevance_category"),
                    "deterministic_interpretation": f.get("engineering_interpretation"),
                    "geometric_reasoning": f.get("reasoning"),
                    "occt_evidence": f.get("evidence", []),
                    "provenance": f.get("provenance", {}),
                }
                for f in feature_graph
            ],
            "classified_dimensions": [
                {
                    "dimension_id": d.get("dimension_id"),
                    "dimension_type": d.get("dimension_type"),
                    "value_mm": d.get("value_mm"),
                    "importance_tier": d.get("importance_tier"),
                    "assigned_view": d.get("assigned_view"),
                    "source_entities": d.get("source_entities", []),
                    "measurement_method": d.get("measurement_method"),
                    "validation_status": d.get("geometric_validation"),
                }
                for d in classified_dimensions
            ],
            "view_intelligence": view_recs,
            "section_intelligence": sec_recs,
            "epistemic_bounds": {
                "known_facts_count": len(feature_graph) + len(classified_dimensions),
                "inferred_interpretations_count": len(feature_graph),
                "not_determinable_from_cad": missing_info,
                "ambiguities_resolved": ambiguities,
            },
        }

    audit = report.audit_summary
    env = audit.get("assembly_envelope_mm", [0.0, 0.0, 0.0])

    package = {
        "metadata": {
            "model_name": report.model_name,
            "pipeline": "CAD_INTELLIGENCE_PHASE_22",
            "kernel": "OpenCASCADE_BRep_Ground_Truth",
        },
        "solid_geometry": {
            "is_brep_valid": True,
            "unique_solids_count": audit.get("unique_solids_count", 1),
            "raw_solids_count": audit.get("total_raw_solids", 1),
            "unique_faces_count": audit.get("unique_faces_count", 0),
            "unique_edges_count": audit.get("unique_edges_count", 0),
            "envelope_mm": {
                "width_x": round(env[0], 3),
                "depth_y": round(env[1], 3),
                "height_z": round(env[2], 3),
            },
            "volume_cm3": round(audit.get("total_volume_cm3", 0.0), 2),
            "surface_area_cm2": round(audit.get("total_surface_area_cm2", 0.0), 2),
            "surface_type_distribution": audit.get("surface_types", {}),
        },
        "ranked_features": [
            {
                "feature_id": f.feature_id,
                "geometric_type": f.geometric_type,
                "source_faces": f.source_faces,
                "source_edges": f.source_edges,
                "measured_dimensions": f.measured_dimensions,
                "relevance_category": f.relevance_category,
                "deterministic_interpretation": f.engineering_interpretation,
                "geometric_reasoning": f.reasoning,
                "occt_evidence": f.evidence,
                "provenance": f.provenance,
            }
            for f in report.feature_graph
        ],
        "classified_dimensions": [
            {
                "dimension_id": d.dimension_id,
                "dimension_type": d.dimension_type,
                "value_mm": d.value_mm,
                "importance_tier": d.importance_tier,
                "assigned_view": d.assigned_view,
                "source_entities": d.source_entities,
                "measurement_method": d.measurement_method,
                "validation_status": d.geometric_validation,
            }
            for d in report.classified_dimensions
        ],
        "view_intelligence": {
            "recommended_primary_views": report.view_recommendations.primary_views,
            "secondary_views": report.view_recommendations.secondary_views,
            "optional_views": report.view_recommendations.optional_views,
            "evaluations": {
                v_name: {
                    "usefulness_score": v.usefulness_score,
                    "rank": v.rank,
                    "rationale": v.engineering_rationale,
                }
                for v_name, v in report.view_recommendations.evaluations.items()
            },
        },
        "section_intelligence": {
            "recommended_primary_section": report.section_recommendations.recommended_primary_section,
            "candidates": [
                {
                    "section_id": s.section_id,
                    "plane_name": s.plane_name,
                    "section_type": s.section_type,
                    "plane_origin": s.plane_origin,
                    "plane_normal": s.plane_normal,
                    "usefulness_score": s.usefulness_score,
                    "exposed_internal_features": s.internal_features_exposed,
                    "cut_edge_count": s.cut_edge_count,
                    "rationale": s.engineering_rationale,
                }
                for s in report.section_recommendations.candidates
            ],
        },
        "epistemic_bounds": {
            "known_facts_count": len(report.feature_graph) + len(report.classified_dimensions),
            "inferred_interpretations_count": len(report.feature_graph),
            "not_determinable_from_cad": report.missing_information,
            "ambiguities_resolved": report.ambiguities_detected,
        },
    }

    return package
