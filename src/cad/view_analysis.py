"""View Visibility Analysis for Dimension Candidates.

Determines, via deterministic orthographic projection geometry, how each
dimension candidate's associated geometry appears in each of the standard
TechDraw orthographic views:

    Front  — camera from -Y (looking +Y)
    Top    — camera from +Z (looking -Z)
    Left   — camera from -X (looking +X)
    Right  — camera from +X (looking -X)
    Bottom — camera from -Z (looking +Z)

Visibility categories:
    circular_profile   — circular shape of cylinder visible (best for diameter dims)
    edge_on            — cylinder appears as pair of lines (axis ⊥ view direction)
    planar_profile     — flat face visible as shape
    occluded           — surface faces away from camera
    unsuitable         — geometry cannot be determined for this view

No dimensions are placed in this module. The module only computes and records
how each candidate's geometry projects into the available views.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.cad.dimensions import DimensionCandidate, DimensionCandidateSet


# ─────────────────────────────────────────────────────────────────────────────
# Standard TechDraw Orthographic View Definitions
# ─────────────────────────────────────────────────────────────────────────────
# Convention: Third-Angle (ASME / ISO)
# Camera direction = the 3D vector pointing FROM camera TOWARD model.
# This matches FreeCAD TechDraw DrawProjGroupItem.Direction exactly.

STANDARD_VIEWS: Dict[str, List[float]] = {
    "Front":  [0.0, -1.0,  0.0],   # looking from +Y toward model
    "Top":    [0.0,  0.0,  1.0],   # looking from -Z downward (FreeCAD convention)
    "Left":   [-1.0, 0.0,  0.0],   # looking from +X toward model
    "Right":  [1.0,  0.0,  0.0],   # looking from -X toward model
    "Bottom": [0.0,  0.0, -1.0],   # looking from +Z upward
}

# Threshold: dot product between axis and view direction
# If |dot| > this, the cylinder appears edge-on in that view.
_EDGE_ON_THRESHOLD = 0.85  # ≈ cos(31.8°)
# If |dot| < this, the cylinder appears as a circular profile.
_CIRCULAR_THRESHOLD = 0.20  # ≈ cos(78.5°)


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ViewVisibility:
    """Visibility classification for one dimension candidate in one view."""
    view: str                    # "Front", "Top", etc.
    visibility: str              # see below
    score: float                 # 0..1 suitability score for placing this dim in this view
    note: str = ""               # short explanation

    # Visibility vocabularly:
    #   circular_profile  — circular cross-section faces the camera → best for Ø dims
    #   edge_on           — cylinder axis is mostly parallel to view direction → shows as lines
    #   planar_profile    — planar surface faces the camera → good for linear dims
    #   partial_profile   — partially visible / oblique angle
    #   unsuitable        — no geometry basis to determine visibility


@dataclass
class CandidateViewAnalysis:
    """Complete view visibility analysis for one dimension candidate."""
    candidate_id: str
    candidate_type: str
    formatted_value: str
    views: List[ViewVisibility]
    recommended_view: Optional[str]   # best single view, or None if ambiguous
    recommended_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ViewAnalysisReport:
    """Complete view analysis for all dimension candidates."""
    total_candidates: int
    analyses: List[CandidateViewAnalysis]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_candidates": self.total_candidates,
            "analyses": [a.to_dict() for a in self.analyses],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Vector utilities
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(v: List[float]) -> List[float]:
    mag = math.sqrt(sum(x**2 for x in v))
    if mag < 1e-9:
        return [0.0, 0.0, 0.0]
    return [x / mag for x in v]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(a[i] * b[i] for i in range(3))


def _abs_dot(a: List[float], b: List[float]) -> float:
    return abs(_dot(_normalize(a), _normalize(b)))


# ─────────────────────────────────────────────────────────────────────────────
# View Analyser
# ─────────────────────────────────────────────────────────────────────────────

class ViewAnalyser:
    """Analyses dimension candidate visibility in each orthographic view."""

    def analyse(self, candidate_set: DimensionCandidateSet) -> ViewAnalysisReport:
        """Compute view visibility for all candidates in the set."""
        analyses: List[CandidateViewAnalysis] = []

        for cand in candidate_set.candidates:
            va = self._analyse_candidate(cand)
            analyses.append(va)

        return ViewAnalysisReport(
            total_candidates=len(analyses),
            analyses=analyses,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Per-candidate dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_candidate(self, cand: DimensionCandidate) -> CandidateViewAnalysis:
        if cand.type in ("diameter", "depth") and cand.axis is not None:
            return self._analyse_cylindrical(cand)
        elif cand.type == "radius" and cand.axis is not None:
            return self._analyse_cylindrical(cand)
        elif cand.type == "linear":
            return self._analyse_linear(cand)
        elif cand.type == "angle":
            return self._analyse_angle(cand)
        else:
            return self._analyse_generic(cand)

    # ─────────────────────────────────────────────────────────────────────────
    # Cylindrical feature (diameter / depth / fillet radius)
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_cylindrical(self, cand: DimensionCandidate) -> CandidateViewAnalysis:
        """Classify each view by how the cylinder axis relates to the view direction.

        Rules:
        - |axis · view_dir| > threshold → edge-on  (axis roughly parallel to view)
        - |axis · view_dir| < threshold → circular profile (axis roughly ⊥ view)
        - Intermediate angles → partial profile
        """
        axis = _normalize(cand.axis)
        views: List[ViewVisibility] = []
        best_view: Optional[str] = None
        best_score = -1.0

        for view_name, view_dir in STANDARD_VIEWS.items():
            vd = _normalize(view_dir)
            dot = _abs_dot(axis, vd)

            if dot >= _EDGE_ON_THRESHOLD:
                # Axis mostly parallel to view direction → circular cross-section faces camera
                vis = "circular_profile"
                score = dot
                note = f"|axis·view|={dot:.3f} — circular cross-section visible"
            elif dot <= _CIRCULAR_THRESHOLD:
                # Axis mostly perpendicular to view direction → edge-on appearance
                vis = "edge_on"
                score = 1.0 - dot  # edge-on is good for depth/length dims
                note = f"|axis·view|={dot:.3f} — appears as bounding rectangle (edge-on)"
            else:
                # Oblique angle — partial profile
                vis = "partial_profile"
                score = 0.3
                note = f"|axis·view|={dot:.3f} — oblique angle, partial visibility"

            # For DEPTH candidates, edge-on is best (you can see the depth along the axis)
            if cand.type == "depth":
                if vis == "edge_on":
                    score = dot * (-1) + 1.0   # higher for more edge-on
                elif vis == "circular_profile":
                    score = 0.1  # depths are hard to show in circular view

            vv = ViewVisibility(
                view=view_name,
                visibility=vis,
                score=round(score, 4),
                note=note,
            )
            views.append(vv)

            if score > best_score:
                best_score = score
                best_view = view_name

        # Build recommendation
        if cand.type in ("diameter", "radius"):
            reason = f"Circular profile visible → dimension can be placed as diameter/radius"
        else:
            reason = f"Edge-on view shows feature depth clearly"

        return CandidateViewAnalysis(
            candidate_id=cand.id,
            candidate_type=cand.type,
            formatted_value=cand.formatted_value,
            views=views,
            recommended_view=best_view,
            recommended_reason=reason,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Linear candidates
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_linear(self, cand: DimensionCandidate) -> CandidateViewAnalysis:
        """Classify views for linear dimensions.

        For a linear dimension along axis A:
        - Views where the measuring axis is roughly perpendicular to the view direction
          → the full length is visible as a horizontal/vertical extent.
        - Views where the measuring axis is parallel to the view direction
          → the feature collapses to a point or line (unsuitable).
        """
        if cand.axis is None:
            return self._analyse_generic(cand)

        axis = _normalize(cand.axis)
        views: List[ViewVisibility] = []
        best_view: Optional[str] = None
        best_score = -1.0

        for view_name, view_dir in STANDARD_VIEWS.items():
            vd = _normalize(view_dir)
            dot = _abs_dot(axis, vd)  # how much axis aligns with view direction

            if dot >= _EDGE_ON_THRESHOLD:
                # Measuring axis goes into/out of camera → length collapses
                vis = "unsuitable"
                score = 0.0
                note = f"|axis·view|={dot:.3f} — dimension collapses in this view"
            elif dot <= _CIRCULAR_THRESHOLD:
                # Measuring axis is in the image plane → full length visible
                vis = "planar_profile"
                score = 1.0 - dot
                note = f"|axis·view|={dot:.3f} — full length visible in this view"
            else:
                vis = "partial_profile"
                score = 0.4
                note = f"|axis·view|={dot:.3f} — partially foreshortened"

            vv = ViewVisibility(view=view_name, visibility=vis, score=round(score, 4), note=note)
            views.append(vv)

            if score > best_score:
                best_score = score
                best_view = view_name

        # If multiple views tie or dimension_semantics is overall_extent, keep the most natural view
        if cand.dimension_semantics == "overall_extent" and best_view is not None:
            reason = "Full extent visible in this view"
        else:
            reason = "Dimension axis lies in image plane — full length visible"

        return CandidateViewAnalysis(
            candidate_id=cand.id,
            candidate_type=cand.type,
            formatted_value=cand.formatted_value,
            views=views,
            recommended_view=best_view,
            recommended_reason=reason,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Angle candidates
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_angle(self, cand: DimensionCandidate) -> CandidateViewAnalysis:
        """Angle between two feature axes — recommend the view where both axes
        project most clearly (both axes approximately in the image plane)."""
        details = cand.details
        axis_a_raw = details.get("axis_a")
        axis_b_raw = details.get("axis_b")

        if not axis_a_raw or not axis_b_raw:
            return self._analyse_generic(cand)

        axis_a = _normalize(axis_a_raw)
        axis_b = _normalize(axis_b_raw)

        views: List[ViewVisibility] = []
        best_view: Optional[str] = None
        best_score = -1.0

        for view_name, view_dir in STANDARD_VIEWS.items():
            vd = _normalize(view_dir)
            dot_a = _abs_dot(axis_a, vd)
            dot_b = _abs_dot(axis_b, vd)

            # Both axes should be in image plane (low dot with view direction)
            # Score = average in-plane-ness
            in_plane_a = 1.0 - dot_a
            in_plane_b = 1.0 - dot_b
            score = (in_plane_a + in_plane_b) / 2.0

            if score > 0.7:
                vis = "planar_profile"
                note = f"Both feature axes in image plane — angle visible"
            elif score > 0.4:
                vis = "partial_profile"
                note = f"One or both axes partially foreshortened"
            else:
                vis = "unsuitable"
                note = f"Axes collapse in this view"

            vv = ViewVisibility(view=view_name, visibility=vis, score=round(score, 4), note=note)
            views.append(vv)

            if score > best_score:
                best_score = score
                best_view = view_name

        return CandidateViewAnalysis(
            candidate_id=cand.id,
            candidate_type=cand.type,
            formatted_value=cand.formatted_value,
            views=views,
            recommended_view=best_view,
            recommended_reason="Both feature axes most visible in this view",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Generic fallback
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_generic(self, cand: DimensionCandidate) -> CandidateViewAnalysis:
        views = [
            ViewVisibility(view=v, visibility="unsuitable", score=0.0,
                           note="No axis information — cannot determine view suitability")
            for v in STANDARD_VIEWS
        ]
        return CandidateViewAnalysis(
            candidate_id=cand.id,
            candidate_type=cand.type,
            formatted_value=cand.formatted_value,
            views=views,
            recommended_view=None,
            recommended_reason="No axis information available for this candidate",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def analyse_view_visibility(candidate_set: DimensionCandidateSet) -> ViewAnalysisReport:
    """Run view visibility analysis for all dimension candidates.

    Args:
        candidate_set: Output from DimensionCandidateEngine.generate().

    Returns:
        ViewAnalysisReport with per-view visibility for every candidate.
    """
    analyser = ViewAnalyser()
    return analyser.analyse(candidate_set)
