"""Phase 17 — Consensus engine: deterministic comparison between Claude and Gemini results.

Disagreements are NEVER resolved automatically. Both models' answers are preserved.
Normalizes equivalent dimension representations (units, symbols, trailing zeros)
while preserving semantic types and drawing view/spatial context.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.drawing.schemas import (
    BoundingBox,
    ConsensusResult,
    ConsensusState,
    DimensionConsensus,
    DimensionType,
    ExtractedDimension,
    ModelResult,
    ViewConsensus,
    ViewType,
)

# Tolerance for considering two numeric values the same (0.5% or 0.01mm)
NUMERIC_TOLERANCE_FRACTION = 0.005
NUMERIC_TOLERANCE_ABS = 0.01


def _values_agree(a: Optional[float], b: Optional[float]) -> bool:
    """Check if two numeric values agree within tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    diff = abs(a - b)
    avg = (abs(a) + abs(b)) / 2
    return diff <= NUMERIC_TOLERANCE_ABS or (avg > 0 and diff / avg <= NUMERIC_TOLERANCE_FRACTION)


def _dim_type_family(dt: DimensionType | str | None) -> str:
    """Group dimension types into semantic families: diameter, radius, angle, depth, chamfer, thread, linear."""
    if dt is None:
        return "unknown"
    val = dt.value.lower() if isinstance(dt, DimensionType) else str(dt).lower().strip()
    if val in ("diameter", "radius", "angle", "depth", "chamfer", "thread"):
        return val
    if val in ("linear", "horizontal", "vertical", "aligned"):
        return "linear"
    return "unknown"


def _clean_raw_text(text: str) -> str:
    """Normalizes raw text representation for comparison:

    - standardizes diameter/radius prefixes (DIA, %%C -> Ø, RAD -> R)
    - strips unit suffixes (mm, inch, in, deg, °)
    - normalizes decimal numbers to eliminate insignificant trailing zeros (e.g. 11.00 -> 11, 24.01 -> 24.01)
    """
    if not text:
        return ""
    s = text.strip()
    # Normalize diameter symbol
    s = re.sub(r'^(dia|%%c|phi)\s*', 'Ø', s, flags=re.IGNORECASE)
    # Strip unit suffixes
    s = re.sub(r'\s*(mm|inch|inches|in|deg|degrees|°)\b', '', s, flags=re.IGNORECASE).strip()

    # Normalize decimal numbers to remove trailing zeros (11.00 -> 11, 24.01 -> 24.01)
    def _norm_num(m: re.Match) -> str:
        try:
            val = float(m.group(0))
            if val.is_integer():
                return str(int(val))
            return f"{val:g}"
        except ValueError:
            return m.group(0)

    s = re.sub(r'\b\d+\.\d+\b', _norm_num, s)
    return s.upper().strip()


def _bbox_center_dist(b1: Optional[BoundingBox], b2: Optional[BoundingBox]) -> Optional[float]:
    """Euclidean distance between bounding box centers (if both present)."""
    if b1 is None or b2 is None:
        return None
    c1_x = (b1.x1 + b1.x2) / 2.0
    c1_y = (b1.y1 + b1.y2) / 2.0
    c2_x = (b2.x1 + b2.x2) / 2.0
    c2_y = (b2.y1 + b2.y2) / 2.0
    return math.hypot(c1_x - c2_x, c1_y - c2_y)


class ConsensusEngine:
    """Compares Claude and Gemini model results deterministically.

    Policy:
    - Identical/equivalent values in corresponding views → AGREED
    - Discrepant values on corresponding features → DISAGREED / UNRESOLVED (both preserved, neither selected)
    - One model detected, other did not → CLAUDE_ONLY / GEMINI_ONLY
    """

    def compare(
        self,
        claude: ModelResult,
        gemini: ModelResult,
    ) -> ConsensusResult:
        """Build a consensus result from two model results."""
        view_result = self._compare_views(claude, gemini)
        dim_result = self._compare_dimensions(claude, gemini)

        total_agreed = len(dim_result["agreed"])
        total_disagreed = len(dim_result["disagreed"])
        total_unresolved = len(dim_result["unresolved"])

        return ConsensusResult(
            agreed_views=view_result["agreed"],
            disagreed_views=view_result["disagreed"],
            agreed_dimensions=dim_result["agreed"],
            disagreed_dimensions=dim_result["disagreed"],
            unresolved_dimensions=dim_result["unresolved"],
            claude_only_dimensions=dim_result["claude_only"],
            gemini_only_dimensions=dim_result["gemini_only"],
            total_claude_dimensions=len(claude.dimensions),
            total_gemini_dimensions=len(gemini.dimensions),
            total_agreed=total_agreed,
            total_disagreed=total_disagreed,
            total_unresolved=total_unresolved,
        )

    # ------------------------------------------------------------------
    # View comparison
    # ------------------------------------------------------------------

    def _compare_views(
        self,
        claude: ModelResult,
        gemini: ModelResult,
    ) -> dict:
        agreed: List[ViewConsensus] = []
        disagreed: List[ViewConsensus] = []

        claude_types = {v.view_type for v in claude.views}
        gemini_types = {v.view_type for v in gemini.views}

        all_types = claude_types | gemini_types

        for vtype in sorted(all_types, key=lambda x: x.value):
            in_claude = vtype in claude_types
            in_gemini = vtype in gemini_types
            claude_id = next(
                (v.view_id for v in claude.views if v.view_type == vtype), None
            )
            gemini_id = next(
                (v.view_id for v in gemini.views if v.view_type == vtype), None
            )

            vc = ViewConsensus(
                view_type=vtype,
                claude_view_id=claude_id,
                gemini_view_id=gemini_id,
                state=(
                    ConsensusState.AGREED
                    if in_claude and in_gemini
                    else ConsensusState.CLAUDE_ONLY
                    if in_claude
                    else ConsensusState.GEMINI_ONLY
                ),
            )

            if in_claude and in_gemini:
                agreed.append(vc)
            else:
                disagreed.append(vc)

        return {"agreed": agreed, "disagreed": disagreed}

    # ------------------------------------------------------------------
    # Dimension comparison with bipartite semantic matching
    # ------------------------------------------------------------------

    def _compare_dimensions(
        self,
        claude: ModelResult,
        gemini: ModelResult,
    ) -> dict:
        """Matches Claude and Gemini dimensions using semantic type, numeric normalization,

        view context, and spatial proximity.
        """
        agreed: List[DimensionConsensus] = []
        disagreed: List[DimensionConsensus] = []
        unresolved: List[DimensionConsensus] = []
        claude_only_texts: List[str] = []
        gemini_only_texts: List[str] = []

        claude_dims = claude.dimensions
        gemini_dims = gemini.dimensions

        # Lookup view types by view_id
        claude_views: Dict[str, ViewType] = {v.view_id: v.view_type for v in claude.views}
        gemini_views: Dict[str, ViewType] = {v.view_id: v.view_type for v in gemini.views}

        # Build candidate score matrix between every Claude and Gemini dimension
        candidates = []
        for ci, c in enumerate(claude_dims):
            c_fam = _dim_type_family(c.dimension_type)
            c_val = c.normalized_value
            c_clean = _clean_raw_text(c.raw_text)
            c_vtype = claude_views.get(c.view_id) if c.view_id else None

            for gi, g in enumerate(gemini_dims):
                g_fam = _dim_type_family(g.dimension_type)
                g_val = g.normalized_value
                g_clean = _clean_raw_text(g.raw_text)
                g_vtype = gemini_views.get(g.view_id) if g.view_id else None

                # Type family compatibility check (diameter != radius != angle != linear)
                if c_fam != "unknown" and g_fam != "unknown" and c_fam != g_fam:
                    continue

                # Check if values agree numerically or through normalized text
                val_agrees = _values_agree(c_val, g_val) or (c_clean == g_clean and len(c_clean) > 0)

                # Check view agreement
                view_agrees = (c_vtype is not None and g_vtype is not None and c_vtype == g_vtype)
                view_conflicts = (c_vtype is not None and g_vtype is not None and c_vtype != g_vtype)

                # Spatial distance
                dist = _bbox_center_dist(c.bbox, g.bbox)

                score = 0.0
                if val_agrees:
                    score += 100.0
                    if view_agrees:
                        score += 30.0
                    elif view_conflicts:
                        score -= 20.0
                    if dist is not None:
                        # Closer annotations get higher priority for duplicate same-value dimensions
                        score += max(0.0, 30.0 - dist / 50.0)
                    candidates.append((score, ci, gi, True))
                else:
                    # Potential value disagreement for the same feature (same view/location + same type)
                    if (view_agrees or (dist is not None and dist < 100.0)) and c_fam == g_fam and c_fam != "unknown":
                        score += 40.0
                        if view_agrees:
                            score += 20.0
                        if dist is not None:
                            score += max(0.0, 30.0 - dist / 50.0)
                        candidates.append((score, ci, gi, False))

        # Sort candidates descending by match score
        candidates.sort(key=lambda x: x[0], reverse=True)

        used_c: Set[int] = set()
        used_g: Set[int] = set()

        for score, ci, gi, val_agrees in candidates:
            if ci in used_c or gi in used_g:
                continue
            used_c.add(ci)
            used_g.add(gi)

            c = claude_dims[ci]
            g = gemini_dims[gi]

            dc = DimensionConsensus(
                claude_raw_text=c.raw_text,
                gemini_raw_text=g.raw_text,
                claude_value=c.normalized_value,
                gemini_value=g.normalized_value,
            )

            if val_agrees:
                dc.state = ConsensusState.AGREED
                agreed.append(dc)
            else:
                # Value disagreement — preserve both, mark UNRESOLVED
                dc.state = ConsensusState.UNRESOLVED
                unresolved.append(dc)

        # Unmatched Claude dimensions
        for ci, c in enumerate(claude_dims):
            if ci not in used_c:
                claude_only_texts.append(c.raw_text)
                disagreed.append(DimensionConsensus(
                    claude_raw_text=c.raw_text,
                    claude_value=c.normalized_value,
                    state=ConsensusState.CLAUDE_ONLY,
                ))

        # Unmatched Gemini dimensions
        for gi, g in enumerate(gemini_dims):
            if gi not in used_g:
                gemini_only_texts.append(g.raw_text)
                disagreed.append(DimensionConsensus(
                    gemini_raw_text=g.raw_text,
                    gemini_value=g.normalized_value,
                    state=ConsensusState.GEMINI_ONLY,
                ))

        return {
            "agreed": agreed,
            "disagreed": disagreed,
            "unresolved": unresolved,
            "claude_only": claude_only_texts,
            "gemini_only": gemini_only_texts,
        }
