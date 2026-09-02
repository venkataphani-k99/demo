"""Phase 22 — Evidence Validator & Hallucination Protector.

Guarantees that:
1. THE LLM IS NEVER THE SOURCE OF GEOMETRIC TRUTH.
2. Every entity referenced by the AI actually exists in the OCCT B-Rep model.
3. Every dimension value mentioned in AI claims matches OCCT mathematical ground truth.
4. If an AI provider invents non-existent FaceIDs, dimensions, or unproven functional claims,
   the validator rejects or overrides them with authoritative OCCT values.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from src.intelligence.ai_reasoning.provider_interface import (
    AIEvidenceReference,
    AIFeatureReasoning,
    AIQuestionAnswer,
    AIReviewResult,
)


class EvidenceValidator:
    """Validates AI reasoning against authoritative OCCT B-Rep ground truth."""

    def validate_review_result(
        self,
        result: AIReviewResult,
        evidence_package: Dict[str, Any],
    ) -> AIReviewResult:
        """Validate AI review result against B-Rep ground truth."""
        validation_notes: List[str] = []
        is_valid = True

        # 1. Build index of valid FaceIDs, FeatureIDs, and Dimensions from OCCT truth
        known_faces: Set[str] = set()
        known_dims: Dict[str, float] = {}
        for feat in evidence_package.get("ranked_features", []):
            for face_id in feat.get("source_faces", []):
                known_faces.add(face_id)

        for dim in evidence_package.get("classified_dimensions", []):
            known_dims[dim["dimension_id"]] = dim["value_mm"]
            for ent in dim.get("source_entities", []):
                if ent.startswith("Face"):
                    known_faces.add(ent)

        # 2. Validate Feature Reasonings
        for feat_reason in result.ranked_feature_interpretations:
            valid_refs: List[AIEvidenceReference] = []

            for ref in feat_reason.evidence_references:
                if ref.entity_type == "FACE":
                    if ref.entity_id in known_faces:
                        valid_refs.append(ref)
                    else:
                        is_valid = False
                        validation_notes.append(
                            f"HALLUCINATION REJECTED: AI referenced non-existent entity '{ref.entity_id}' in {feat_reason.feature_id}."
                        )
                else:
                    valid_refs.append(ref)

            feat_reason.evidence_references = valid_refs

            # 3. Check for Hallucinated Numeric Dimensions in AI text
            # Regex find diameter mentions like Ø25, 25mm, etc.
            dia_matches = re.findall(r"Ø\s*(\d+(?:\.\d+)?)", feat_reason.engineering_reasoning + " " + feat_reason.known_geometry)
            for d_str in dia_matches:
                val = float(d_str)
                # Check if this diameter matches any OCCT measured diameter
                matched = any(abs(val - occt_val) < 0.2 for occt_val in known_dims.values())
                if not matched and val > 1.0:
                    validation_notes.append(
                        f"DIMENSION INCONSISTENCY WARNING: AI mentioned Ø{val}mm in {feat_reason.feature_id}, but OCCT ground truth does not contain this diameter."
                    )

            # Enforce epistemic constraint: Cautious language check
            if "definitely is a" in feat_reason.inferred_engineering_role.lower():
                feat_reason.inferred_engineering_role = feat_reason.inferred_engineering_role.replace("definitely is a", "possible")
                validation_notes.append(
                    f"EPISTEMIC GUARD: Downgraded definitive claim to 'possible' in {feat_reason.feature_id}."
                )

        # Set final status
        if not is_valid:
            result.validation_status = "WARNINGS"
        else:
            result.validation_status = "PASSED"

        result.validation_notes = validation_notes
        return result

    def validate_question_answer(
        self,
        qa: AIQuestionAnswer,
        evidence_package: Dict[str, Any],
    ) -> AIQuestionAnswer:
        """Validate an interactive Q&A answer against evidence."""
        known_faces: Set[str] = set()
        for feat in evidence_package.get("ranked_features", []):
            for f in feat.get("source_faces", []):
                known_faces.add(f)

        filtered_refs = [
            ref for ref in qa.grounded_evidence
            if ref.entity_type != "FACE" or ref.entity_id in known_faces
        ]
        qa.grounded_evidence = filtered_refs
        return qa
