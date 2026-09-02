"""Phase 25 — Consistency Engine.

Orchestrates the complete CAD ↔ Drawing Consistency and Design Review.
Evaluates dimension coverage, section alignment, conflicts, missing features,
and produces the auditable ConsistencyAuditSummary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.intelligence.drawing_consistency.cad_drawing_matcher import CADDrawingMatcher
from src.intelligence.drawing_consistency.drawing_evidence_extractor import DrawingEvidenceExtractor
from src.intelligence.drawing_consistency.drawing_evidence_model import (
    CADDrawingMatchItem,
    ConsistencyAuditSummary,
    ConsistencyStatus,
    DrawingEvidencePackage,
)


class ConsistencyEngine:
    """Core consistency audit engine for CAD and Engineering Drawings."""

    @staticmethod
    def audit_consistency(
        cad_features: List[Dict[str, Any]],
        cad_dimensions: List[Dict[str, Any]],
        drawing_package: DrawingEvidencePackage,
    ) -> Tuple[List[CADDrawingMatchItem], ConsistencyAuditSummary]:
        """Runs full deterministic consistency evaluation."""
        matches = CADDrawingMatcher.match_cad_to_drawing(
            cad_features=cad_features,
            cad_dimensions=cad_dimensions,
            drawing_package=drawing_package,
        )

        consistent_count = sum(1 for m in matches if m.consistency_status == ConsistencyStatus.CONSISTENT)
        conflict_count = sum(1 for m in matches if m.consistency_status == ConsistencyStatus.CONFLICT)
        cannot_verify_count = sum(1 for m in matches if m.consistency_status == ConsistencyStatus.CANNOT_VERIFY)
        missing_count = sum(1 for m in matches if m.consistency_status == ConsistencyStatus.MISSING)
        ambiguous_count = sum(1 for m in matches if m.consistency_status == ConsistencyStatus.AMBIGUOUS)

        total_cad = len(cad_features)
        total_dwg = len(drawing_package.dimensions)
        coverage_pct = (consistent_count / max(1, total_dwg)) * 100.0

        summary = ConsistencyAuditSummary(
            total_cad_features_audited=total_cad,
            total_drawing_dimensions_found=total_dwg,
            matched_count=len(matches),
            consistent_count=consistent_count,
            conflict_count=conflict_count,
            cannot_verify_count=cannot_verify_count,
            missing_count=missing_count,
            ambiguous_count=ambiguous_count,
            dimension_coverage_percent=round(coverage_pct, 1),
        )

        return matches, summary
