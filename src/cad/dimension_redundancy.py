"""Dimension Redundancy and Feature Coverage Analysis Engine.

Detects over-dimensioning and duplicate dimension candidates:
1. Filters derived and redundant candidates so the drawing is not over-constrained.
2. Performs feature-by-feature engineering coverage analysis:
   - fully_dimensioned    (all required size/depth parameters defined)
   - partially_dimensioned (some size parameters defined, location/depth pending)
   - not_dimensioned      (no placed dimensions)
   - ambiguous            (geometry exists but semantics are incomplete)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.cad.dimensions import DimensionCandidate, DimensionCandidateSet
from src.cad.dimension_dependencies import DependencyAnalysisResult, DimensionDependencyNode
from src.cad.features import RecognizedFeature


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureCoverageItem:
    """Coverage status for a single recognized engineering feature."""
    feature_id: str
    feature_type: str
    coverage_status: str                  # "fully_dimensioned" | "partially_dimensioned" | "not_dimensioned" | "ambiguous"
    dimension_ids: List[str]              # all associated dimension IDs
    placed_dimension_ids: List[str]       # dimensions actually placed on the drawing
    missing_aspects: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RedundancyAnalysisResult:
    """Complete redundancy and coverage report."""
    total_candidates: int
    independent_count: int
    derived_count: int
    constraint_count: int
    redundant_count: int
    ambiguous_count: int
    feature_coverages: List[FeatureCoverageItem]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_candidates": self.total_candidates,
            "independent_count": self.independent_count,
            "derived_count": self.derived_count,
            "constraint_count": self.constraint_count,
            "redundant_count": self.redundant_count,
            "ambiguous_count": self.ambiguous_count,
            "feature_coverages": [f.to_dict() for f in self.feature_coverages],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Redundancy & Coverage Analyser
# ─────────────────────────────────────────────────────────────────────────────

class DimensionRedundancyAnalyser:
    """Evaluates redundancy across dimension candidate sets and evaluates feature coverage."""

    def analyse(
        self,
        candidate_set: DimensionCandidateSet,
        dependency_result: DependencyAnalysisResult,
        features: List[RecognizedFeature],
        placed_dim_ids: Optional[Set[str]] = None,
    ) -> RedundancyAnalysisResult:
        """Evaluate redundancy and compute feature engineering coverage."""
        placed_set = placed_dim_ids or set()
        nodes = dependency_result.nodes

        # 1. Feature-by-feature coverage
        coverages: List[FeatureCoverageItem] = []

        # Index candidates by feature_id, feature_group, and constituent source_features
        feat_cands: Dict[str, List[DimensionCandidate]] = {}
        for c in candidate_set.candidates:
            fids = []
            if c.source_feature:
                fids.append(c.source_feature)
            if c.feature_group:
                fids.append(c.feature_group)
            if "source_features" in c.details:
                fids.extend(c.details["source_features"])

            for fid in fids:
                if c not in feat_cands.setdefault(fid, []):
                    feat_cands[fid].append(c)

        for feat in features:
            fid = feat.feature_id
            cands = feat_cands.get(fid, [])
            all_ids = [c.id for c in cands]
            placed_ids = [cid for cid in all_ids if cid in placed_set]

            status, missing = self._evaluate_feature_coverage(feat, cands, placed_ids)

            coverages.append(FeatureCoverageItem(
                feature_id=fid,
                feature_type=feat.feature_type,
                coverage_status=status,
                dimension_ids=all_ids,
                placed_dimension_ids=placed_ids,
                missing_aspects=missing,
            ))

        # Also add Overall Size coverage
        overall_cands = [c for c in candidate_set.candidates if c.dimension_semantics == "overall_extent"]
        overall_ids = [c.id for c in overall_cands]
        overall_placed = [cid for cid in overall_ids if cid in placed_set]
        overall_status = "fully_dimensioned" if len(overall_placed) >= 3 else "partially_dimensioned" if overall_placed else "not_dimensioned"

        coverages.append(FeatureCoverageItem(
            feature_id="OVERALL_SIZE",
            feature_type="bounding_box",
            coverage_status=overall_status,
            dimension_ids=overall_ids,
            placed_dimension_ids=overall_placed,
            missing_aspects=[] if overall_status == "fully_dimensioned" else ["incomplete_extents"],
            notes=["Overall bounding envelope dimensions (X, Y, Z)"],
        ))

        ambiguous = sum(1 for c in candidate_set.candidates if c.status == "ambiguous")

        return RedundancyAnalysisResult(
            total_candidates=candidate_set.total,
            independent_count=dependency_result.independent_count,
            derived_count=dependency_result.derived_count,
            constraint_count=dependency_result.constraint_count,
            redundant_count=dependency_result.redundant_count,
            ambiguous_count=ambiguous,
            feature_coverages=coverages,
        )

    def _evaluate_feature_coverage(
        self,
        feat: RecognizedFeature,
        candidates: List[DimensionCandidate],
        placed_ids: List[str],
    ) -> Tuple[str, List[str]]:
        """Determine whether a feature is fully or partially defined by placed dimensions."""
        ftype = feat.feature_type
        missing: List[str] = []

        if ftype == "counterbored_hole":
            # Requires bore dia, cbore dia, and depths
            has_bore = any("bore_diameter" in str(c.details) for c in candidates if c.id in placed_ids)
            has_cbore = any("counterbore_diameter" in str(c.details) for c in candidates if c.id in placed_ids)
            has_depth = any(c.type == "depth" for c in candidates if c.id in placed_ids)

            if not has_bore: missing.append("bore_diameter")
            if not has_cbore: missing.append("counterbore_diameter")
            if not has_depth: missing.append("depth")

            # Note: location (X/Y hole center) is a separate location dimension
            missing.append("location_coordinates")

            if not placed_ids:
                return "not_dimensioned", missing
            elif len(missing) == 1 and missing[0] == "location_coordinates":
                return "fully_dimensioned", missing
            else:
                return "partially_dimensioned", missing

        elif ftype == "through_hole":
            has_dia = any(c.type == "diameter" for c in candidates if c.id in placed_ids)
            has_len = any(c.type == "linear" for c in candidates if c.id in placed_ids)

            if not has_dia: missing.append("diameter")
            if not has_len: missing.append("length")
            missing.append("location_coordinates")

            if not placed_ids:
                return "not_dimensioned", missing
            elif len(missing) == 1 and missing[0] == "location_coordinates":
                return "fully_dimensioned", missing
            else:
                return "partially_dimensioned", missing

        elif ftype == "external_boss":
            has_dia = any(c.type == "diameter" for c in candidates if c.id in placed_ids)
            has_len = any(c.type == "linear" for c in candidates if c.id in placed_ids)

            if not has_dia: missing.append("diameter")
            if not has_len: missing.append("axial_length")

            if not placed_ids:
                return "not_dimensioned", missing
            elif not missing:
                return "fully_dimensioned", missing
            else:
                return "partially_dimensioned", missing

        elif ftype in ("fillet", "toroidal_corner_blend"):
            has_r = any(c.type == "radius" for c in candidates if c.id in placed_ids)
            if has_r:
                return "fully_dimensioned", []
            else:
                return "partially_dimensioned", ["blend_radius"]

        elif ftype == "internal_bore":
            # For BORE_003: partial arc
            if feat.dimensions.get("angular_sweep_deg", 360) < 180:
                return "ambiguous", ["partial_arc_sweep", "incompletely_bounded"]
            else:
                return "partially_dimensioned", ["length"]

        return "partially_dimensioned", missing
