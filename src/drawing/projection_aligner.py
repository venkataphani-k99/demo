"""Phase 18.1 — Evidence-Driven Orthographic Projection Aligner.

Maps 2D orthographic dimensions to 3D axes based on orientation and view geometry,
preserving uncertainty when orientation cannot be definitively established.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from src.drawing.schemas import (
    AxisAssignment,
    CrossViewAlignment,
    DimensionType,
    ExtractedDimension,
    ViewType,
)


def _determine_orientation(d: ExtractedDimension) -> str:
    """Determines dimension orientation ('HORIZONTAL', 'VERTICAL', or 'AMBIGUOUS')."""
    dtype = d.dimension_type.value.lower() if isinstance(d.dimension_type, DimensionType) else str(d.dimension_type).lower()
    if dtype == "horizontal":
        return "HORIZONTAL"
    if dtype == "vertical":
        return "VERTICAL"

    # Use bbox aspect ratio if available
    if d.bbox:
        w = d.bbox.x2 - d.bbox.x1
        h = d.bbox.y2 - d.bbox.y1
        if h > 0:
            aspect = w / h
            if aspect > 1.35:
                return "HORIZONTAL"
            if aspect < 0.75:
                return "VERTICAL"

    return "AMBIGUOUS"


class ProjectionAligner:
    """Aligns orthographic 2D drawing dimensions with 3D coordinate axes."""

    def align(
        self,
        dimensions: List[ExtractedDimension],
        views_map: Dict[str, ViewType],
    ) -> CrossViewAlignment:
        """Aligns dimensions to 3D axes (X, Y, Z) and computes envelope.

        Parameters
        ----------
        dimensions : List[ExtractedDimension]
            Extracted/agreed dimensions.
        views_map : Dict[str, ViewType]
            Mapping from view_id to ViewType.

        Returns
        -------
        CrossViewAlignment
            Axis-aligned dimensions, uncertainties, and computed 3D envelope.
        """
        x_dims: List[str] = []
        y_dims: List[str] = []
        z_dims: List[str] = []
        unassigned: List[str] = []
        axis_uncertainty: Dict[str, str] = {}

        x_vals: List[float] = []
        y_vals: List[float] = []
        z_vals: List[float] = []

        for d in dimensions:
            raw_text = d.raw_text
            val = d.normalized_value
            vtype = views_map.get(d.view_id, ViewType.UNKNOWN) if d.view_id else ViewType.UNKNOWN
            dtype = d.dimension_type.value.lower() if isinstance(d.dimension_type, DimensionType) else str(d.dimension_type).lower()

            # Diameters and radii represent local cylinder/arc geometry
            if "diameter" in dtype or "ø" in raw_text.lower() or "radius" in dtype or raw_text.upper().startswith("R"):
                unassigned.append(raw_text)
                axis_uncertainty[raw_text] = f"Radial/Cylindrical callout in view {vtype.value}; represents feature diameter/radius, not linear coordinate axis."
                continue

            orient = _determine_orientation(d)

            # Map view + orientation to primary 3D axis
            if vtype == ViewType.FRONT:
                if orient == "HORIZONTAL":
                    x_dims.append(raw_text)
                    if val is not None and val > 0:
                        x_vals.append(val)
                elif orient == "VERTICAL":
                    z_dims.append(raw_text)
                    if val is not None and val > 0:
                        z_vals.append(val)
                else:
                    unassigned.append(raw_text)
                    axis_uncertainty[raw_text] = f"XZ_FRONT: FRONT view dimension orientation ambiguous (w={val}). Probable X or Z."
            elif vtype in (ViewType.TOP, ViewType.BOTTOM):
                if orient == "HORIZONTAL":
                    x_dims.append(raw_text)
                    if val is not None and val > 0:
                        x_vals.append(val)
                elif orient == "VERTICAL":
                    y_dims.append(raw_text)
                    if val is not None and val > 0:
                        y_vals.append(val)
                else:
                    unassigned.append(raw_text)
                    axis_uncertainty[raw_text] = f"XY_{vtype.value}: {vtype.value} view dimension orientation ambiguous (w={val}). Probable X or Y."
            elif vtype in (ViewType.LEFT, ViewType.RIGHT):
                if orient == "HORIZONTAL":
                    y_dims.append(raw_text)
                    if val is not None and val > 0:
                        y_vals.append(val)
                elif orient == "VERTICAL":
                    z_dims.append(raw_text)
                    if val is not None and val > 0:
                        z_vals.append(val)
                else:
                    unassigned.append(raw_text)
                    axis_uncertainty[raw_text] = f"YZ_{vtype.value}: {vtype.value} view dimension orientation ambiguous (w={val}). Probable Y or Z."
            else:
                unassigned.append(raw_text)
                axis_uncertainty[raw_text] = f"UNKNOWN_VIEW: Dimension has unassigned or unknown view context."

        # Deduplicate dimension lists preserving order
        def _dedup(seq: List[str]) -> List[str]:
            seen: Set[str] = set()
            out = []
            for item in seq:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

        envelope: Dict[str, Optional[float]] = {
            "width_x": max(x_vals) if x_vals else None,
            "depth_y": max(y_vals) if y_vals else None,
            "height_z": max(z_vals) if z_vals else None,
        }

        return CrossViewAlignment(
            width_x_dimensions=_dedup(x_dims),
            depth_y_dimensions=_dedup(y_dims),
            height_z_dimensions=_dedup(z_dims),
            axis_uncertainty=axis_uncertainty,
            unassigned_dimensions=_dedup(unassigned),
            estimated_envelope_3d=envelope,
        )
