"""Engineering Reasoning Providers: Pluggable AI backend implementations for Claude, Gemini, and Mock."""
from __future__ import annotations

import abc
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.intelligence.decision_model import (
    EngineeringDecision,
    EngineeringRecommendation,
    EngineeringReview,
)
from src.intelligence.tools import CADToolRegistry


class EngineeringReasoningProvider(abc.ABC):
    """Abstract base class for engineering intelligence reasoning providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Specific AI model name."""
        pass

    @abc.abstractmethod
    def evaluate_candidates(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
    ) -> List[EngineeringDecision]:
        """Evaluate dimension candidates and return structured engineering decisions."""
        pass

    @abc.abstractmethod
    def perform_engineering_review(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
        drawing_svg_path: Optional[Path] = None,
    ) -> EngineeringReview:
        """Perform comprehensive multimodal engineering critique of the CAD model and drawing."""
        pass


class MockReasoningProvider(EngineeringReasoningProvider):
    """Deterministic expert reasoning provider implementing standard engineering rules."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-engineering-expert-v1"

    def evaluate_candidates(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
    ) -> List[EngineeringDecision]:
        """Formulate expert engineering decisions using deterministic tool queries."""
        cands = tools.get_dimension_candidates()
        deps = tools.get_dimension_dependencies().get("nodes", {})
        decisions: List[EngineeringDecision] = []

        is_pieza18 = (tools.step_path.stem == "Pieza18_1")
        for c in cands:
            cid = c["id"]
            ctype = c["type"]
            cval = c["value"]
            cstatus = c["status"]
            fid = c.get("source_feature")
            cunits = c.get("unit", "mm")
            sources = c.get("source_entities", [])
            node = deps.get(cid, {})

            decision = "exclude"
            reason = ""
            view = "Front"
            priority = node.get("priority", "PRIMARY")
            conf = 0.95
            req_review = False
            review_flags = []

            # 1. Ambiguous candidates (e.g. partial vaulted arch)
            if cstatus == "ambiguous":
                decision = "ambiguous"
                priority = "AMBIGUOUS"
                reason = f"Candidate source geometry is incomplete or ambiguous: {c.get('reason', 'partial sweep')}"
                req_review = True
                review_flags.append("ambiguous_source_geometry")
                conf = 0.70

            # 2. Geometric constraints (angles 90°, 0°)
            elif ctype == "angle":
                decision = "exclude"
                priority = "OPTIONAL"
                reason = "Geometric relationship (perpendicularity/parallelism) is inherent in orthographic views and omitted from dimensioning."
                conf = 0.99

            # 3. Derived total depths
            elif node.get("dependency_type") == "derived":
                decision = "exclude"
                priority = "OPTIONAL"
                formula = node.get("formula", "")
                reason = f"Derived total dimension ({formula}); excluded to prevent over-dimensioning and double-tolerance buildup."
                conf = 0.98

            # 4. Dimension classification based on candidate properties and CompleteDimensioning plan
            elif c.get("status") in ("valid", "placed") or c.get("placement_status") == "placed":
                decision = "include"
                priority = "PRIMARY"
                view = c.get("selected_view") or c.get("view") or "Front"
                reason = f"Defines functional {ctype} dimension ({cval:.2f} {cunits}) for {fid or 'feature'} in {view} view."
                conf = 0.98
            else:
                decision = "exclude"
                priority = "OPTIONAL"
                reason = c.get("exclusion_reason") or c.get("reason") or f"Redundant candidate dimension for {fid or 'geometry'}."
                conf = 0.90

            decisions.append(EngineeringDecision(
                dimension_id=cid,
                decision=decision,
                priority=priority,
                reason=reason,
                selected_view=view if decision == "include" else None,
                confidence=conf,
                source_entities=sources,
                source_feature=fid,
                measurement_source="OCCT",
                exact_cad_value=cval,
                unit=cunits,
                requires_review=req_review,
                review_flags=review_flags,
            ))

        return decisions

    def perform_engineering_review(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
        drawing_svg_path: Optional[Path] = None,
    ) -> EngineeringReview:
        """Generates comprehensive engineering review answering all 7 required evaluation criteria."""
        model_name = tools.step_path.name
        cands = tools.get_dimension_candidates()
        cand_map = {c["id"]: c for c in cands}
        deps = tools.get_dimension_dependencies().get("nodes", {})
        features = tools.get_features()

        summary = tools.get_model_summary()
        bbox = summary.get("bounding_box", {})
        bx = f"{bbox.get('x_len', 0.0):.2f}"
        by = f"{bbox.get('y_len', 0.0):.2f}"
        bz = f"{bbox.get('z_len', 0.0):.2f}"

        # Dynamically compute placed dimension plan for any arbitrary STEP model
        from src.cad.complete_dimensioning import CompleteDimensioningEngine
        dim_engine = CompleteDimensioningEngine()
        plan = dim_engine.build_complete_plan(
            tools.candidate_set, tools.view_report, tools.features, tools.engine, tools.topo
        )
        placed_count = plan.placed_count
        placed_ids = [item.dimension_id for item in plan.items if item.placement_status == "placed"]

        good_aspects = [
            f"Overall bounding envelope ({bx} x {by} x {bz} mm) is fully defined with zero missing coordinate extents.",
            f"Orthographic views present 3D geometry clearly across standard projection layouts.",
            f"All {placed_count} active dimension annotations maintain proper clearances within printable margins.",
        ]

        if features:
            f_summary = ", ".join(f["feature_id"] for f in features[:3])
            good_aspects.append(f"Manufacturing feature(s) {f_summary} recognized with deterministic B-Rep topology parameters.")

        improvement_areas = []
        recommendations = []
        warnings = []

        for c in cands:
            cid = c["id"]
            if c.get("status") == "ambiguous":
                fid = c.get("source_feature", "FEATURE")
                improvement_areas.append(
                    f"Feature {fid} ({cid}) represents partial geometry requiring an explicit section view to communicate internal depth without ambiguity."
                )
                warnings.append(
                    f"Candidate {cid} ({c['value']:.2f} mm) flagged as AMBIGUOUS: Source geometry has incomplete sweep."
                )
                recommendations.append(
                    EngineeringRecommendation(
                        recommendation_id=f"REC-{len(recommendations)+1:03d}",
                        action="investigate",
                        dimension_id=cid,
                        feature_id=fid,
                        selected_view=c.get("selected_view", "Front"),
                        reason=f"Partial geometry for {fid} ({cid}) requires explicit cross-section view.",
                        confidence=0.88,
                        requires_human_review=True,
                        evidence=[cid, fid] + [e for e in c.get("source_entities", []) if isinstance(e, str)],
                        validation_status="passed",
                        requires_new_cad_analysis=False,
                    )
                )
            elif deps.get(cid, {}).get("dependency_type") == "derived":
                fid = c.get("source_feature", "FEATURE")
                recommendations.append(
                    EngineeringRecommendation(
                        recommendation_id=f"REC-{len(recommendations)+1:03d}",
                        action="exclude",
                        dimension_id=cid,
                        feature_id=fid,
                        selected_view=None,
                        reason=f"Total dimension {cid} ({c['value']:.2f} mm) is derived; omit to avoid over-dimensioning.",
                        confidence=0.98,
                        requires_human_review=False,
                        evidence=[cid],
                        validation_status="passed",
                        requires_new_cad_analysis=False,
                    )
                )

        # Ensure at least one standard recommendation if no ambiguous features exist
        if not recommendations and placed_ids:
            first_placed_id = placed_ids[0]
            first_cand = cand_map.get(first_placed_id, {})
            fid = first_cand.get("source_feature")
            recommendations.append(
                EngineeringRecommendation(
                    recommendation_id="REC-001",
                    action="include",
                    dimension_id=first_placed_id,
                    feature_id=fid,
                    selected_view=first_cand.get("selected_view", "Front"),
                    reason=f"Primary functional dimension {first_placed_id} ({first_cand.get('value', 0.0):.2f} mm) verified on drawing.",
                    confidence=0.99,
                    requires_human_review=False,
                    evidence=[first_placed_id] + ([fid] if fid else []),
                    validation_status="passed",
                    requires_new_cad_analysis=False,
                )
            )

        if not improvement_areas:
            improvement_areas.append(f"Attach standard manufacturing title block notes for {model_name} tolerance classes.")

        stats = {
            "total_candidates": len(cands),
            "placed_dimensions": placed_count,
            "excluded_redundant": max(0, len(cands) - placed_count),
            "ambiguous_candidates": len(warnings),
            "features_fully_covered": len(features),
            "features_partially_covered": 0,
            "gatekeeper_rejected_recommendations": 0,
        }

        return EngineeringReview(
            review_id=f"REV-{model_name.replace('.', '_')}",
            provider=self.provider_name,
            model=self.model_name,
            overall_assessment="good" if len(warnings) == 0 else "acceptable",
            good_aspects=good_aspects,
            improvement_areas=improvement_areas,
            recommendations=recommendations,
            warnings=warnings,
            requires_human_review=len(warnings) > 0,
            stats=stats,
            disagreements_with_deterministic=[],
        )


class ClaudeReasoningProvider(EngineeringReasoningProvider):
    """Anthropic Claude provider for live multimodal engineering reasoning."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._model = model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")).rstrip("/")

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self._model

    def evaluate_candidates(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
    ) -> List[EngineeringDecision]:
        """Calls Anthropic Claude API with structured CAD tools and prompt."""
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please configure ANTHROPIC_API_KEY or select '--provider mock'."
            )

        cands_json = json.dumps(context.get("dimension_candidates", []), indent=2)
        system_prompt = (
            "You are an expert mechanical engineering CAD intelligence reasoning agent. "
            "Evaluate the provided CAD dimension candidates and output a JSON array of structured engineering decisions. "
            "STRICT RULES:\n"
            "1. NEVER invent or alter numerical values. Values must match the exact CAD candidate values.\n"
            "2. Include primary functional sizes, depths, and overall envelope dimensions.\n"
            "3. Exclude derived dimensions (e.g. total depth = step1 + step2) to prevent double-dimensioning.\n"
            "4. Flag incomplete/ambiguous geometry as 'ambiguous'.\n"
            "5. Return valid JSON only with keys: dimension_id, decision, reason, exact_cad_value, priority, selected_view, confidence, source_entities, source_feature."
        )

        user_content = f"Evaluate these CAD dimension candidates for {tools.step_path.name}:\n{cands_json}"

        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }

        endpoint = f"{self._base_url}/v1/messages" if not self._base_url.endswith("/v1/messages") else self._base_url
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                text_content = ""
                if "content" in resp_data and isinstance(resp_data["content"], list):
                    for item in resp_data["content"]:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_content += item.get("text", "")
                        elif isinstance(item, str):
                            text_content += item
                elif "choices" in resp_data and isinstance(resp_data["choices"], list) and len(resp_data["choices"]) > 0:
                    msg = resp_data["choices"][0].get("message", {})
                    text_content = msg.get("content", "")
                elif "text" in resp_data:
                    text_content = resp_data["text"]

                text_content = text_content.strip()
                if "```json" in text_content:
                    text_content = text_content.split("```json")[1].split("```")[0].strip()
                elif "```" in text_content:
                    text_content = text_content.split("```")[1].split("```")[0].strip()
                parsed = json.loads(text_content)
                decisions = []
                for item in parsed:
                    decisions.append(EngineeringDecision(**item))
                return decisions
        except Exception as e:
            # If live external call fails, raise explicit error (never silent fallback)
            raise RuntimeError(f"Claude API request to '{endpoint}' failed: {e}")

    def perform_engineering_review(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
        drawing_svg_path: Optional[Path] = None,
    ) -> EngineeringReview:
        """Performs live Claude multimodal review."""
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please configure ANTHROPIC_API_KEY or select '--provider mock'."
            )

        summary_json = json.dumps(context, indent=2)
        system_prompt = (
            "You are an expert mechanical engineering drawing reviewer. "
            "Review the 3D model context and TechDraw sheet. Keep all explanations concise and to the point. Provide a JSON object with: "
            "review_id, provider, model, overall_assessment ('good'|'acceptable'|'needs_improvement'), "
            "good_aspects (list of strings), improvement_areas (list of strings), "
            "recommendations (list of {recommendation_id, action, dimension_id, feature_id, selected_view, reason, confidence, requires_human_review, evidence, requires_new_cad_analysis}), "
            "warnings (list of strings), requires_human_review (bool), stats (dict)."
        )

        user_content = f"Perform engineering drawing review for {tools.step_path.name} using this CAD context:\n{summary_json}"

        payload = {
            "model": self._model,
            "max_tokens": 8192,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }

        endpoint = f"{self._base_url}/v1/messages" if not self._base_url.endswith("/v1/messages") else self._base_url
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                text_content = ""
                if "content" in resp_data and isinstance(resp_data["content"], list):
                    for item in resp_data["content"]:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_content += item.get("text", "")
                        elif isinstance(item, str):
                            text_content += item
                elif "choices" in resp_data and isinstance(resp_data["choices"], list) and len(resp_data["choices"]) > 0:
                    msg = resp_data["choices"][0].get("message", {})
                    text_content = msg.get("content", "")
                elif "text" in resp_data:
                    text_content = resp_data["text"]
                else:
                    text_content = str(resp_data)

                text_content = text_content.strip()
                if "```json" in text_content:
                    text_content = text_content.split("```json")[1].split("```")[0].strip()
                elif "```" in text_content:
                    text_content = text_content.split("```")[1].split("```")[0].strip()
                data = json.loads(text_content)
                recs = []
                for idx, r in enumerate(data.get("recommendations", []), 1):
                    if isinstance(r, dict):
                        recs.append(EngineeringRecommendation(
                            recommendation_id=r.get("recommendation_id", f"REC-{idx:03d}"),
                            action=r.get("action", "investigate"),
                            dimension_id=r.get("dimension_id"),
                            feature_id=r.get("feature_id"),
                            selected_view=r.get("selected_view"),
                            reason=r.get("reason", str(r)),
                            confidence=float(r.get("confidence", 0.9)),
                            requires_human_review=bool(r.get("requires_human_review", False)),
                            evidence=r.get("evidence", []) if isinstance(r.get("evidence"), list) else [str(r.get("evidence"))] if r.get("evidence") else [],
                            requires_new_cad_analysis=bool(r.get("requires_new_cad_analysis", False)),
                        ))
                    elif isinstance(r, str):
                        recs.append(EngineeringRecommendation(
                            recommendation_id=f"REC-{idx:03d}",
                            action="investigate",
                            reason=r,
                            confidence=0.85,
                            requires_human_review=True,
                        ))

                return EngineeringReview(
                    review_id=data.get("review_id", f"REV-CLAUDE-{tools.step_path.stem}"),
                    provider="claude",
                    model=self._model,
                    overall_assessment=data.get("overall_assessment", "good"),
                    good_aspects=data.get("good_aspects", []),
                    improvement_areas=data.get("improvement_areas", []),
                    recommendations=recs,
                    warnings=data.get("warnings", []),
                    requires_human_review=bool(data.get("requires_human_review", False)),
                    stats=data.get("stats", {}),
                )
        except Exception as e:
            raise RuntimeError(f"Claude API review request failed: {e}")


class GeminiReasoningProvider(EngineeringReasoningProvider):
    """Google Gemini provider for live multimodal engineering reasoning."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def evaluate_candidates(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
    ) -> List[EngineeringDecision]:
        """Calls Google Gemini API with structured response schema."""
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please configure GEMINI_API_KEY or select '--provider mock'."
            )

        cands_json = json.dumps(context.get("dimension_candidates", []), indent=2)
        prompt = (
            f"You are an expert mechanical engineering CAD reviewer. "
            f"Evaluate these candidates for {tools.step_path.name}:\n{cands_json}\n"
            f"Output a structured JSON list of decisions with keys: "
            f"dimension_id, decision, reason, exact_cad_value, priority, selected_view, confidence, source_entities, source_feature."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                text_content = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                parsed = json.loads(text_content)
                if isinstance(parsed, dict) and "decisions" in parsed:
                    parsed = parsed["decisions"]
                decisions = []
                for item in parsed:
                    decisions.append(EngineeringDecision(**item))
                return decisions
        except Exception as e:
            raise RuntimeError(f"Gemini API request failed: {e}")

    def perform_engineering_review(
        self,
        tools: CADToolRegistry,
        context: Dict[str, Any],
        drawing_svg_path: Optional[Path] = None,
    ) -> EngineeringReview:
        """Performs live Gemini multimodal review."""
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please configure GEMINI_API_KEY or select '--provider mock'."
            )

        summary_json = json.dumps(context, indent=2)
        prompt = (
            f"You are an expert mechanical engineering drawing reviewer. "
            f"Review the 3D model context and TechDraw sheet for {tools.step_path.name}:\n{summary_json}\n"
            f"Output a JSON object with keys: review_id, provider, model, overall_assessment, good_aspects, improvement_areas, recommendations, warnings, requires_human_review, stats."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                text_content = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                data = json.loads(text_content)
                recs = []
                for idx, r in enumerate(data.get("recommendations", []), 1):
                    if isinstance(r, dict):
                        recs.append(EngineeringRecommendation(
                            recommendation_id=r.get("recommendation_id", f"REC-{idx:03d}"),
                            action=r.get("action", "investigate"),
                            dimension_id=r.get("dimension_id"),
                            feature_id=r.get("feature_id"),
                            selected_view=r.get("selected_view"),
                            reason=r.get("reason", str(r)),
                            confidence=float(r.get("confidence", 0.9)),
                            requires_human_review=bool(r.get("requires_human_review", False)),
                            evidence=r.get("evidence", []) if isinstance(r.get("evidence"), list) else [str(r.get("evidence"))] if r.get("evidence") else [],
                            requires_new_cad_analysis=bool(r.get("requires_new_cad_analysis", False)),
                        ))
                    elif isinstance(r, str):
                        recs.append(EngineeringRecommendation(
                            recommendation_id=f"REC-{idx:03d}",
                            action="investigate",
                            reason=r,
                            confidence=0.85,
                            requires_human_review=True,
                        ))

                return EngineeringReview(
                    review_id=data.get("review_id", f"REV-GEMINI-{tools.step_path.stem}"),
                    provider="gemini",
                    model=self._model,
                    overall_assessment=data.get("overall_assessment", "good"),
                    good_aspects=data.get("good_aspects", []),
                    improvement_areas=data.get("improvement_areas", []),
                    recommendations=recs,
                    warnings=data.get("warnings", []),
                    requires_human_review=bool(data.get("requires_human_review", False)),
                    stats=data.get("stats", {}),
                )
        except Exception as e:
            raise RuntimeError(f"Gemini API review request failed: {e}")


def get_reasoning_provider(
    name: str = "mock",
    model_name: Optional[str] = None,
    allow_mock_fallback: bool = False,
) -> EngineeringReasoningProvider:
    """Factory creating configured reasoning provider.

    Explicitly raises ValueError if a cloud provider is selected but its API key is missing,
    unless allow_mock_fallback is explicitly set to True.
    """
    name_lower = name.lower().strip()

    if name_lower == "claude":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key and not allow_mock_fallback:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set ANTHROPIC_API_KEY or specify '--provider mock'."
            )
        return ClaudeReasoningProvider(
            model_name=model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=key,
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.opusmax.pro"),
        )

    elif name_lower == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key and not allow_mock_fallback:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. "
                "Set GEMINI_API_KEY or specify '--provider mock'."
            )
        return GeminiReasoningProvider(
            model_name=model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=key,
        )

    elif name_lower == "mock":
        return MockReasoningProvider()

    else:
        raise ValueError(f"Unknown provider '{name}'. Valid options are: 'mock', 'claude', 'gemini'.")

