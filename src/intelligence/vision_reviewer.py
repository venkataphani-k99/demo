"""Multimodal Drawing Vision Reviewer: Critiques rendered TechDraw sheets for presentation quality."""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.intelligence.decision_model import EngineeringDecision, VisionReviewResult


class DrawingVisionReviewer(abc.ABC):
    """Abstract base class for multimodal drawing inspection."""

    @abc.abstractmethod
    def review_drawing(
        self,
        svg_or_image_path: Path,
        engineering_context: Dict[str, Any],
        decisions: List[EngineeringDecision],
    ) -> VisionReviewResult:
        """Critique drawing layout, annotations, and visual clarity."""
        pass


class MockDrawingVisionReviewer(DrawingVisionReviewer):
    """Deterministic visual reviewer checking rendered drawing file metrics and text distribution."""

    def review_drawing(
        self,
        svg_or_image_path: Path,
        engineering_context: Dict[str, Any],
        decisions: List[EngineeringDecision],
    ) -> VisionReviewResult:
        """Analyze rendered drawing metrics."""
        svg_path = Path(svg_or_image_path)
        issues: List[str] = []
        missing: List[str] = []
        notes: List[str] = []
        req_review = False

        if not svg_path.exists():
            issues.append(f"Drawing visual artifact {svg_path.name} not found on disk")
            req_review = True
        else:
            file_size = svg_path.stat().st_size
            notes.append(f"Rendered vector drawing verified ({file_size:,} bytes)")

        # Count placed decisions
        included = [d for d in decisions if d.decision == "include"]
        if len(included) < 5:
            missing.append("Drawing contains fewer than 5 dimensions; check for un-annotated features")
            req_review = True
        else:
            notes.append(f"Sheet contains {len(included)} active dimension annotations")

        # Check for un-dimensioned features
        feats = engineering_context.get("features", [])
        included_features = {d.source_feature for d in included if d.source_feature}
        for f in feats:
            fid = f.get("feature_id")
            if fid and fid not in included_features and f.get("feature_type") != "internal_bore":
                missing.append(f"Feature {fid} has no placed dimensions on sheet")

        # Evaluate readability
        readability = "high" if not issues and len(missing) == 0 else "acceptable" if not issues else "poor"

        return VisionReviewResult(
            readability=readability,
            visual_issues=issues,
            missing_visible_annotations=missing,
            requires_review=req_review,
            notes=notes,
        )
