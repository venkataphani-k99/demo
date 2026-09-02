"""Phase 18 — Constraint Analyzer: evaluates dimension completeness and constraint coverage."""
from __future__ import annotations

from typing import Dict, List, Tuple
from src.drawing.schemas import DrawingFeature, FeatureGraph, FeatureParameter


class ConstraintAnalyzer:
    """Evaluates whether mechanical features have complete parametric definitions."""

    def analyze(self, feature_graph: FeatureGraph) -> Dict[str, any]:
        """Calculates constraint score and identifies fully vs partially constrained features."""
        features = feature_graph.features
        total = len(features)
        if total == 0:
            return {
                "completeness_score": 0.0,
                "fully_constrained_count": 0,
                "partially_constrained_count": 0,
                "status": "under_constrained",
            }

        fully_constrained = 0
        partially_constrained = 0

        for f in features:
            if len(f.parameters) >= 1 and all(p.value > 0 for p in f.parameters):
                fully_constrained += 1
            else:
                partially_constrained += 1

        score = fully_constrained / total if total > 0 else 0.0
        status = "fully_constrained" if score >= 0.9 else "partially_constrained" if score >= 0.5 else "under_constrained"

        return {
            "completeness_score": round(score, 2),
            "fully_constrained_count": fully_constrained,
            "partially_constrained_count": partially_constrained,
            "status": status,
        }
