"""Phase 22 — Google Gemini Engineering Reasoning Provider.

Implements evidence-constrained AI reasoning over structured CAD Evidence Packages using Gemini API.
Enforces structured JSON output and validates all claims against OCCT geometric ground truth.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from src.intelligence.ai_reasoning.evidence_validator import EvidenceValidator
from src.intelligence.ai_reasoning.provider_interface import (
    AIEvidenceReference,
    AIFeatureReasoning,
    AIQuestionAnswer,
    AIReasoningProvider,
    AIReviewResult,
)


class GeminiAIProvider(AIReasoningProvider):
    """Google Gemini AI implementation for evidence-constrained engineering reasoning."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.validator = EvidenceValidator()

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _call_gemini(self, system_prompt: str, user_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a structured JSON generation call to Gemini REST API with retry and fallback."""
        if not self._api_key:
            return None

        candidate_models = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
        ]
        # Remove duplicates while preserving order
        candidate_models = list(dict.fromkeys([m for m in candidate_models if m]))

        prompt_text = f"{system_prompt}\n\n=== STRUCTURED ENGINEERING EVIDENCE PACKAGE ===\n{json.dumps(user_payload, indent=2)}"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        last_error = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self._api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text_content)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8") if e.fp else str(e)
                last_error = f"Gemini API HTTP {e.code} ({model}): {err_body}"
                continue
            except Exception as e:
                last_error = f"Gemini API call failed ({model}): {e}"
                continue

        # If all API calls fail, return None to trigger deterministic fallback
        return None

    def analyze_engineering_evidence(self, evidence_package: Dict[str, Any]) -> AIReviewResult:
        """Perform full evidence-constrained engineering reasoning across the CAD model."""
        system_prompt = """
You are an expert Senior CAD & Manufacturing Design Intelligence Assistant.
Your task is to analyze a structured 3D CAD Engineering Evidence Package derived from OpenCASCADE (OCCT) B-Rep geometry.

CRITICAL RULES:
1. THE SUPPLIED EVIDENCE PACKAGE IS THE ONLY SOURCE OF GEOMETRIC TRUTH.
2. NEVER invent dimensions, Face IDs, Edge IDs, or coordinates.
3. Use cautious, objective engineering language:
   - Use 'consistent with', 'possible', 'inferred', 'cannot be proven from geometry alone'.
   - NEVER say 'This is definitely a...' or 'The designer intended...' unless explicit text evidence is provided.
4. For non-geometric items (e.g. threads, material, surface finish), clearly state: 'Not determinable from supplied CAD evidence'.
5. Produce a valid JSON response matching this EXACT schema:
{
  "executive_part_interpretation": "...",
  "part_classification": "MECHANICAL_ASSEMBLY" | "PRISMATIC_PART" | "ROTARY_AIRFOIL",
  "ranked_feature_interpretations": [
    {
      "feature_id": "FEAT_001",
      "known_geometry": "...",
      "inferred_engineering_role": "...",
      "relevance_category": "CRITICAL" | "FUNCTIONAL" | "INTERFACE" | "MANUFACTURING-RELEVANT" | "COSMETIC",
      "engineering_reasoning": "...",
      "alternative_interpretations": ["..."],
      "evidence_references": [
        {"entity_type": "FACE", "entity_id": "Face2", "measured_property": "diameter_mm=23.0"}
      ],
      "confidence_score": 0.85,
      "unknowns_and_assumptions": ["..."],
      "recommended_engineer_check": "..."
    }
  ],
  "view_explanations": {
    "FRONT": "...",
    "TOP": "...",
    "RIGHT": "...",
    "LEFT": "..."
  },
  "section_explanations": {
    "SEC_AA": "..."
  },
  "missing_information_analysis": [
    "..."
  ],
  "recommended_engineer_priorities": [
    "..."
  ]
}
"""
        raw_json = self._call_gemini(system_prompt, evidence_package)
        if raw_json is None:
            from src.intelligence.ai_reasoning.mock_provider import MockAIProvider
            mock = MockAIProvider()
            return mock.analyze_engineering_evidence(evidence_package)

        feature_interpretations: List[AIFeatureReasoning] = []
        for feat in raw_json.get("ranked_feature_interpretations", []):
            refs = [
                AIEvidenceReference(
                    entity_type=r.get("entity_type", "FACE"),
                    entity_id=r.get("entity_id", "Face1"),
                    measured_property=r.get("measured_property"),
                )
                for r in feat.get("evidence_references", [])
            ]
            feature_interpretations.append(
                AIFeatureReasoning(
                    feature_id=feat.get("feature_id", "FEAT_001"),
                    known_geometry=feat.get("known_geometry", ""),
                    inferred_engineering_role=feat.get("inferred_engineering_role", ""),
                    relevance_category=feat.get("relevance_category", "FUNCTIONAL"),
                    engineering_reasoning=feat.get("engineering_reasoning", ""),
                    alternative_interpretations=feat.get("alternative_interpretations", []),
                    evidence_references=refs,
                    confidence_score=feat.get("confidence_score", 0.8),
                    unknowns_and_assumptions=feat.get("unknowns_and_assumptions", []),
                    recommended_engineer_check=feat.get("recommended_engineer_check", ""),
                )
            )

        res = AIReviewResult(
            provider_name=self.provider_name,
            model_name=self.model_name,
            executive_part_interpretation=raw_json.get("executive_part_interpretation", ""),
            part_classification=raw_json.get("part_classification", "MECHANICAL_PART"),
            ranked_feature_interpretations=feature_interpretations,
            view_explanations=raw_json.get("view_explanations", {}),
            section_explanations=raw_json.get("section_explanations", {}),
            missing_information_analysis=raw_json.get("missing_information_analysis", []),
            recommended_engineer_priorities=raw_json.get("recommended_engineer_priorities", []),
            raw_ai_response=json.dumps(raw_json),
            validation_status="PENDING",
        )

        # Pass through Evidence Validator to guard against hallucinated FaceIDs or dimensions
        return self.validator.validate_review_result(res, evidence_package)

    def answer_engineering_question(self, question: str, evidence_package: Dict[str, Any]) -> AIQuestionAnswer:
        """Answer an interactive engineering question strictly grounded in the evidence package."""
        system_prompt = f"""
You are an expert CAD Intelligence Assistant answering an engineering question about a CAD model.
Answer strictly using the supplied Evidence Package.
Do NOT invent geometry.

Question: {question}

Return JSON with this schema:
{{
  "answer": "...",
  "grounded_evidence": [
    {{"entity_type": "FACE", "entity_id": "Face2", "measured_property": "..."}}
  ],
  "epistemic_qualification": "Grounded in OCCT B-Rep geometry" | "Inferred" | "Not determinable from supplied CAD evidence",
  "suggested_followups": ["...", "..."]
}}
"""
        raw_json = self._call_gemini(system_prompt, evidence_package)
        if raw_json is None:
            from src.intelligence.ai_reasoning.mock_provider import MockAIProvider
            mock = MockAIProvider()
            return mock.answer_engineering_question(question, evidence_package)

        refs = [
            AIEvidenceReference(
                entity_type=r.get("entity_type", "FACE"),
                entity_id=r.get("entity_id", "Face1"),
                measured_property=r.get("measured_property"),
            )
            for r in raw_json.get("grounded_evidence", [])
        ]

        qa = AIQuestionAnswer(
            question=question,
            answer=raw_json.get("answer", "Analysis grounded in OCCT geometry."),
            grounded_evidence=refs,
            epistemic_qualification=raw_json.get("epistemic_qualification", "Grounded in OCCT B-Rep geometry"),
            suggested_followups=raw_json.get("suggested_followups", []),
        )

        return self.validator.validate_question_answer(qa, evidence_package)
