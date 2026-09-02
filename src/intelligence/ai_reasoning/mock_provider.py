"""Phase 22 — Deterministic Mock AI Reasoning Provider.

Provides rock-solid mock reasoning responses for automated testing without network access.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.intelligence.ai_reasoning.provider_interface import (
    AIEvidenceReference,
    AIFeatureReasoning,
    AIQuestionAnswer,
    AIReasoningProvider,
    AIReviewResult,
)


class MockAIProvider(AIReasoningProvider):
    """Deterministic Mock implementation of AIReasoningProvider for test suites."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-engineering-reasoner-v1"

    def analyze_engineering_evidence(self, evidence_package: Dict[str, Any]) -> AIReviewResult:
        model_name = evidence_package.get("metadata", {}).get("model_name", "model.step")
        features = evidence_package.get("ranked_features", [])

        feature_interpretations: List[AIFeatureReasoning] = []
        for feat in features[:8]:
            f_id = feat["feature_id"]
            g_type = feat["geometric_type"]
            faces = feat.get("source_faces", [])
            dims = feat.get("measured_dimensions", {})
            d_val = dims.get("diameter_mm", dims.get("step_width_mm", 0.0))

            if "INTERNAL_CYLINDER" in g_type:
                inferred = "POSSIBLE FUNCTIONAL INTERFACE / FLOW CONDUIT"
                reason = "Internal cylindrical conduit oriented along principal flow axis with adjacent mounting boundary."
                cat = "CRITICAL" if d_val > 20.0 else "FUNCTIONAL"
            elif "EXTERNAL_CYLINDER" in g_type:
                inferred = "POSSIBLE MOUNTING SHAFT / STEM"
                reason = "Protruding external cylindrical boss with open axial access."
                cat = "FUNCTIONAL"
            else:
                inferred = "POSSIBLE MATING / MOUNTING FACE"
                reason = "Planar boundary surface perpendicular to cylinder axis."
                cat = "INTERFACE"

            feature_interpretations.append(
                AIFeatureReasoning(
                    feature_id=f_id,
                    known_geometry=f"{g_type} with dimensions {dims}",
                    inferred_engineering_role=inferred,
                    relevance_category=cat,
                    engineering_reasoning=reason,
                    alternative_interpretations=["Clearance passage", "Locating feature"],
                    evidence_references=[
                        AIEvidenceReference(entity_type="FACE", entity_id=f_id_item, measured_property=f"dim={d_val}")
                        for f_id_item in faces
                    ],
                    confidence_score=0.85,
                    unknowns_and_assumptions=["Thread specification not determinable from pure STEP geometry"],
                    recommended_engineer_check="Verify mating interface specification and tolerance fit requirements.",
                )
            )

        view_explanations = {
            "FRONT": "Exposes primary envelope width × height and orthogonal feature arrangements.",
            "TOP": "Exposes plan depth and true-size circular cylindrical orientations.",
            "RIGHT": "Exposes lateral profile and coaxial bore alignment.",
            "LEFT": "Largely redundant with RIGHT for symmetric lateral geometry.",
        }

        section_explanations = {
            "SEC_AA": "Recommended because it cuts along the central flow axis and reveals internal cavities hidden from exterior views."
        }

        return AIReviewResult(
            provider_name=self.provider_name,
            model_name=self.model_name,
            executive_part_interpretation=f"The geometry of {model_name} is consistent with a mechanical assembly possessing cylindrical conduits and mounting interfaces.",
            part_classification="MECHANICAL_ASSEMBLY",
            ranked_feature_interpretations=feature_interpretations,
            view_explanations=view_explanations,
            section_explanations=section_explanations,
            missing_information_analysis=[
                "Thread pitch and standard are not determinable from supplied pure STEP AP214 B-Rep geometry.",
                "Surface finish Ra and material hardness require manufacturing drawing notes.",
            ],
            recommended_engineer_priorities=[
                "Inspect primary internal bore interfaces for flow conduit sealing requirements.",
                "Verify minimum pressure wall thickness on Section A-A.",
                "Confirm thread specification on internal through-ports.",
            ],
            raw_ai_response='{"status": "mock_success"}',
            validation_status="PASSED",
        )

    def answer_engineering_question(self, question: str, evidence_package: Dict[str, Any]) -> AIQuestionAnswer:
        q_lower = question.lower()
        features = evidence_package.get("ranked_features", [])

        if "missing" in q_lower or "unknown" in q_lower or "not in step" in q_lower:
            return AIQuestionAnswer(
                question=question,
                answer=(
                    "1. Thread Specifications: STEP AP214 models geometry only; internal through-bores Face2 and Face4 (Ø23.000 mm) do not indicate whether they are BSPP, NPT, or ISO metric threads.\n"
                    "2. Manufacturing Tolerances: No fit classes (e.g. H7/g6 or ±0.02 mm) exist in pure neutral B-Rep geometry.\n"
                    "3. Material & Metallurgy: Material grade (e.g. Stainless Steel AISI 316) and hardness specifications require 2D drawing title block notes or an external Mill Test Report (MTR).\n"
                    "4. Surface Finish: Sealing face roughness (Ra 0.8 / Ra 1.6) is absent from the 3D solid file."
                ),
                grounded_evidence=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face2", measured_property="Ø23.00 mm (Bore)"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face4", measured_property="Ø23.00 mm (Bore)"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face7", measured_property="Ø35.00 mm (Seat)"),
                ],
                epistemic_qualification="Epistemic Classification: Explicitly UNKNOWN from neutral ISO 10303 STEP AP214 B-Rep geometry.",
                suggested_followups=["What should I inspect first?", "Why was Section A-A recommended?", "What dimensions are critical?"],
            )

        if "inspect" in q_lower or "first" in q_lower or "priority" in q_lower:
            return AIQuestionAnswer(
                question=question,
                answer=(
                    "1. Priority 1 — Minimum Wall Thickness (1.80 mm): Inspect Section A-A where internal fluid bore Face4 (Ø23.000 mm) passes closest to external mounting flange Face22 (34.20 mm step) to ensure pressure containment safety.\n"
                    "2. Priority 2 — Coaxial Bore Alignment: Verify concentricity between inlet Face2 and outlet Face4 (both Ø23.000 mm) to guarantee leak-free valve flow.\n"
                    "3. Priority 3 — Central Seat Cavity (Face7, Ø35.000 mm): Check for proper clearance and spherical seat concentricity before machining."
                ),
                grounded_evidence=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face4", measured_property="Ø23.00 mm (Internal Bore)"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face22", measured_property="34.20 mm (Flange Interface)"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face7", measured_property="Ø35.00 mm (Seat Chamber)"),
                ],
                epistemic_qualification="Grounded in OCCT Analytical B-Rep Geometry and Proximity Analysis.",
                suggested_followups=["Why was Section A-A recommended?", "What is missing from this STEP?", "What dimensions are critical?"],
            )

        if "section" in q_lower or "cut" in q_lower or "sec_aa" in q_lower:
            return AIQuestionAnswer(
                question=question,
                answer=(
                    "Section A-A (longitudinal cutting plane at Z = 5.91 mm, Normal [0, 0, 1]) is recommended because it cuts directly along the central flow axis. "
                    "This exposes 8 internal occluded cavities—including Ø23.000 mm bores (Face2, Face4) and the central Ø35.000 mm valve seat chamber (Face7)—that are completely hidden from external views. "
                    "It also exposes the critical 1.80 mm minimum wall thickness boundary against external flange Face22."
                ),
                grounded_evidence=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face4", measured_property="Ø23.00 mm"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face7", measured_property="Ø35.00 mm"),
                    AIEvidenceReference(entity_type="FACE", entity_id="Face22", measured_property="34.20 mm"),
                ],
                epistemic_qualification="Grounded in OCCT Plane-Surface Intersection Truth.",
                suggested_followups=["What should I inspect first?", "What is missing from this STEP?"],
            )

        if "face2" in q_lower or "face 2" in q_lower:
            return AIQuestionAnswer(
                question=question,
                answer=(
                    "Face 2 is an internal Ø23.000 mm cylindrical surface forming the primary longitudinal fluid inlet/outlet port (FEAT_001). "
                    "Inferred Role: Primary fluid conduit consistent with a ball valve body. "
                    "Drawing Definition: The 2D drawing specifies 'Ø23.00 ±0.02 mm' (DRAW_DIM_001) in Front view, agreeing with CAD truth. "
                    "Unknown from STEP: Thread pitch (e.g. BSPP/NPT), seal surface finish Ra, and operating pressure rating."
                ),
                grounded_evidence=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face2", measured_property="Ø23.00 mm (OCCT GeomCylinder)"),
                ],
                epistemic_qualification="Grounded in OCCT Analytical B-Rep Geometry.",
                suggested_followups=["What is Face7 actually doing?", "What should I inspect first?"],
            )

        if "face7" in q_lower or "face 7" in q_lower or "chamber" in q_lower:
            return AIQuestionAnswer(
                question=question,
                answer=(
                    "Face 7 is an expanded internal cylindrical cavity of Ø35.000 mm (FEAT_003). "
                    "Inferred Role: Central valve seat chamber designed to house a rotating valve ball and elastomer seat rings. "
                    "Drawing Definition: Shown in Section A-A as 'Ø35.00 ±0.05 mm' (DRAW_DIM_002), matching CAD nominal geometry. "
                    "Unknown from STEP: Seat bevel angle, elastomeric O-ring groove depth, and ball clearance tolerances."
                ),
                grounded_evidence=[
                    AIEvidenceReference(entity_type="FACE", entity_id="Face7", measured_property="Ø35.00 mm (OCCT GeomCylinder)"),
                ],
                epistemic_qualification="Grounded in OCCT Analytical B-Rep Geometry.",
                suggested_followups=["Why was Section A-A recommended?", "What is Face2 actually doing?"],
            )

        top_feat = features[0] if features else {}
        top_faces = top_feat.get("source_faces", ["Face2"])

        return AIQuestionAnswer(
            question=question,
            answer=(
                "This STEP model represents a precision industrial valve body assembly (Envelope: 114.0 × 71.5 × 56.2 mm). "
                "The primary flow conduit is defined by coaxial cylindrical through-bores Face2 and Face4 (Ø23.000 mm), "
                "housing a central spherical chamber Face7 (Ø35.000 mm) for the internal valve seat. "
                "External planar surfaces Face22 and Face34 form mounting flanges (34.20 mm step), while Face24 (Ø4.000 mm) acts as the actuator stem pin. "
                "The 2D drawing verifies these nominal dimensions with 52.6% coverage, while material specification (SS316) requires external MTR certification."
            ),
            grounded_evidence=[
                AIEvidenceReference(entity_type="FACE", entity_id=f, measured_property="OCCT_GeomCylinder")
                for f in top_faces
            ],
            epistemic_qualification="Grounded strictly in OCCT B-Rep analytical geometry.",
            suggested_followups=["What should I inspect first?", "What is missing from this STEP?", "Why was Section A-A recommended?"],
        )

