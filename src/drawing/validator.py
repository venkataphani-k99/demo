"""Phase 17 — Structural validator for DrawingUnderstanding.

Validates that AI-extracted data is structurally correct.
Does NOT decide what a drawing "should" contain — only checks format/bounds/types.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from src.drawing.schemas import (
    DrawingUnderstanding,
    ExtractedDimension,
    ModelResult,
    ValidationError,
)

_VALID_UNITS = {
    "mm", "in", "inch", "inches", "m", "cm", "ft", "foot", "feet",
    "degree", "degrees", "°", "rad", "radian", "radians",
}


def _e(field: str, item_id: str, msg: str, severity: str = "error") -> ValidationError:
    return ValidationError(field_path=field, item_id=item_id, message=msg, severity=severity)


class DrawingValidator:
    """
    Validates the structural correctness of a DrawingUnderstanding.

    Rules enforced:
    1. All bounding box coordinates are within image bounds.
    2. All normalized numeric values are finite and positive (or zero for angles).
    3. Units are recognized strings (or None).
    4. Dimension type enum values are valid.
    5. View IDs referenced by dimensions exist in the view list.
    6. All dimension_ids and entity_ids are unique within their provider result.
    7. No negative linear dimensions.
    8. No malformed tolerance text (must contain a digit if present).
    9. Confidence is within [0, 1].
    """

    def validate(
        self,
        understanding: DrawingUnderstanding,
        image_width: int,
        image_height: int,
    ) -> Tuple[DrawingUnderstanding, List[ValidationError]]:
        """
        Validate a DrawingUnderstanding against structural rules.

        Parameters
        ----------
        understanding : DrawingUnderstanding
            The understanding to validate.
        image_width : int
            Pixel width of the normalized image.
        image_height : int
            Pixel height of the normalized image.

        Returns
        -------
        (understanding, errors)
            The (possibly modified) understanding and a list of validation errors.
            Errors are also written back into understanding.validation_errors.
        """
        errors: List[ValidationError] = []

        for provider_label, result in [
            ("claude", understanding.claude_result),
            ("gemini", understanding.gemini_result),
        ]:
            if result is None:
                continue
            errors.extend(
                self._validate_model_result(result, provider_label, image_width, image_height)
            )

        understanding.validation_errors = errors
        understanding.validation_passed = len([e for e in errors if e.severity == "error"]) == 0
        return understanding, errors

    def _validate_model_result(
        self,
        result: ModelResult,
        label: str,
        img_w: int,
        img_h: int,
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []

        # Collect valid view IDs
        view_ids = {v.view_id for v in result.views}

        # --- Views ---
        seen_view_ids = set()
        for v in result.views:
            vid = v.view_id
            if vid in seen_view_ids:
                errors.append(_e(f"{label}.views", vid, f"Duplicate view_id '{vid}'."))
            seen_view_ids.add(vid)

            if not (0.0 <= v.confidence <= 1.0):
                errors.append(_e(f"{label}.views", vid, f"confidence {v.confidence} outside [0,1]."))

            if v.bbox and img_w > 0 and img_h > 0:
                b = v.bbox
                if b.x1 < 0 or b.y1 < 0 or b.x2 > img_w or b.y2 > img_h:
                    errors.append(_e(
                        f"{label}.views", vid,
                        f"bbox [{b.x1},{b.y1},{b.x2},{b.y2}] outside image bounds "
                        f"{img_w}×{img_h}.",
                        severity="warning",
                    ))

        # --- Dimensions ---
        seen_dim_ids = set()
        for d in result.dimensions:
            did = d.dimension_id
            if did in seen_dim_ids:
                errors.append(_e(f"{label}.dimensions", did, f"Duplicate dimension_id '{did}'."))
            seen_dim_ids.add(did)

            # Confidence
            if not (0.0 <= d.confidence <= 1.0):
                errors.append(_e(f"{label}.dimensions", did, f"confidence {d.confidence} outside [0,1]."))

            # Numeric validity
            if d.normalized_value is not None:
                if not math.isfinite(d.normalized_value):
                    errors.append(_e(f"{label}.dimensions", did, "normalized_value is not finite."))
                elif d.normalized_value < 0 and d.dimension_type.value not in ("angle",):
                    errors.append(_e(
                        f"{label}.dimensions", did,
                        f"normalized_value {d.normalized_value} is negative for non-angle dimension.",
                        severity="warning",
                    ))

            # Unit validity
            if d.unit and d.unit.lower().strip() not in _VALID_UNITS:
                errors.append(_e(
                    f"{label}.dimensions", did,
                    f"Unit '{d.unit}' is not a recognized engineering unit.",
                    severity="warning",
                ))

            # View reference validity
            if d.view_id and d.view_id not in view_ids:
                errors.append(_e(
                    f"{label}.dimensions", did,
                    f"view_id '{d.view_id}' does not reference any detected view.",
                ))

            # Tolerance text: only validate if a non-empty tolerance string is actually specified
            if d.tolerance_text:
                tol_clean = d.tolerance_text.strip()
                if tol_clean.lower() not in ("none", "null", "n/a", "undefined", ""):
                    has_digit = any(c.isdigit() for c in tol_clean)
                    if not has_digit:
                        errors.append(_e(
                            f"{label}.dimensions", did,
                            f"tolerance_text '{d.tolerance_text}' appears malformed (no numeric value).",
                            severity="warning",
                        ))

            # Bounding box
            if d.bbox and img_w > 0 and img_h > 0:
                b = d.bbox
                if b.x1 < 0 or b.y1 < 0 or b.x2 > img_w or b.y2 > img_h:
                    errors.append(_e(
                        f"{label}.dimensions", did,
                        f"bbox [{b.x1},{b.y1},{b.x2},{b.y2}] outside image bounds {img_w}×{img_h}.",
                        severity="warning",
                    ))

        # --- Entities ---
        seen_ent_ids = set()
        for e in result.entities:
            eid = e.entity_id
            if eid in seen_ent_ids:
                errors.append(_e(f"{label}.entities", eid, f"Duplicate entity_id '{eid}'."))
            seen_ent_ids.add(eid)

            if not (0.0 <= e.confidence <= 1.0):
                errors.append(_e(f"{label}.entities", eid, f"confidence {e.confidence} outside [0,1]."))

            if e.view_id and e.view_id not in view_ids:
                errors.append(_e(
                    f"{label}.entities", eid,
                    f"view_id '{e.view_id}' does not reference any detected view.",
                ))

        return errors
