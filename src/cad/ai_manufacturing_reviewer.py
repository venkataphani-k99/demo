"""Phase M1.14 — AI Manufacturing & Moldability Review Layer.

Receives ONLY structured deterministic B-Rep evidence from the Manufacturing Intelligence Engine
and generates a prioritized engineering review report with exact citations:
- Top manufacturing review priorities ranked by severity
- Explanations of what is known, what is inferred, and what remains unknown
- Alternative tooling interpretations
- Actionable review steps for design/tooling engineers
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.cad.mfg_evidence_model import (
    EpistemicState,
    FindingCategory,
    ManufacturingFinding,
    SeverityLevel,
)
from src.cad.mold_analyzer import ManufacturingReport


@dataclass
class ReviewPriorityItem:
    priority_rank: int
    severity: str
    title: str
    finding_id: str
    source_entities: List[str]
    known_geometric_fact: str
    inferred_manufacturing_implication: str
    unknown_factors: List[str]
    alternative_interpretations: List[str]
    recommended_engineer_action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIManufacturingReviewReport:
    executive_summary: str
    process_assumption: str
    selected_pull_direction: str
    top_priorities: List[ReviewPriorityItem]
    epistemic_provenance: Dict[str, int]
    general_tooling_guidelines: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executive_summary": self.executive_summary,
            "process_assumption": self.process_assumption,
            "selected_pull_direction": self.selected_pull_direction,
            "top_priorities": [p.to_dict() for p in self.top_priorities],
            "epistemic_provenance": self.epistemic_provenance,
            "general_tooling_guidelines": self.general_tooling_guidelines,
        }


class AIManufacturingReviewer:
    """Consumes deterministic manufacturing findings to produce prioritized engineering review agendas."""

    @classmethod
    def generate_review(cls, report: ManufacturingReport) -> AIManufacturingReviewReport:
        findings = report.findings
        preset_name = report.preset_used.get("display_name", "General Plastic Injection")
        pull_dir_name = report.optimal_direction_name

        # Rank findings by severity: CRITICAL first, then WARNING, then INFO
        severity_order = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.WARNING: 1,
            SeverityLevel.INFO: 2,
            SeverityLevel.ACCEPTABLE: 3,
        }
        sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 99))

        priorities: List[ReviewPriorityItem] = []
        for idx, f in enumerate(sorted_findings[:7], 1):
            # Extract known geometric facts from deterministic dict
            known_facts_str = ", ".join(f"{k}: {v}" for k, v in f.known_geometry.items())

            # Generate alternative interpretations
            alt_interps: List[str] = []
            if f.category == FindingCategory.POTENTIAL_SIDE_ACTION:
                alt_interps.append("Redesign part with a bypass core shut-off window to eliminate side-action slide.")
                alt_interps.append("Evaluate 2-stage ejection or split-cavity parting plane re-alignment.")
            elif f.category == FindingCategory.DRAFT_DEFICIENCY:
                alt_interps.append("If high-polish finish (SPI A2) is specified, lower draft may be acceptable with specialized ejector layout.")
                alt_interps.append("Apply textured grain taper expansion if cosmetic grain is required.")
            elif f.category == FindingCategory.WALL_THICKNESS_CONCERN:
                alt_interps.append("Add coring pockets on B-side to reduce mass while preserving stiffness.")
                alt_interps.append("Increase gate pressure and packing time if heavy section cannot be cored.")
            elif f.category == FindingCategory.TRANSVERSE_CORE_PIN:
                alt_interps.append("Re-orient hole parallel to draw direction to mold with stationary core pin.")
                alt_interps.append("Post-mold drilling/machining operation if production volume is low.")

            priorities.append(ReviewPriorityItem(
                priority_rank=idx,
                severity=f.severity.value,
                title=f.title,
                finding_id=f.finding_id,
                source_entities=f.source_entities,
                known_geometric_fact=f"Geometric Fact: {f.geometric_reasoning} ({known_facts_str})",
                inferred_manufacturing_implication=f.engineering_interpretation,
                unknown_factors=f.unknowns,
                alternative_interpretations=alt_interps,
                recommended_engineer_action=f.recommended_engineer_action,
            ))

        # Executive Summary
        exec_summary = (
            f"Manufacturing review completed under process profile '{preset_name}' along preferred draw vector '{pull_dir_name}'. "
            f"Evaluated {report.total_faces} B-Rep faces with {len(report.insufficient_draft_faces)} draft violations, "
            f"{len(report.undercut_faces)} undercut faces, and {len(report.transverse_holes)} transverse passages. "
            f"Estimated press requirement is {report.estimated_clamping_tonnage:.0f} Tonnes at {report.estimated_cavity_pressure_bar:.0f} bar."
        )

        guidelines = [
            f"Verify that all cosmetic Class-A faces satisfy the minimum {report.preset_used.get('min_draft_deg', 1.5)}° draft threshold.",
            "Review candidate side-actions for potential elimination via core pass-through shut-offs.",
            "Confirm ejector pin contact surfaces are located on Core side and away from cosmetic Cavity boundaries.",
            "Inspect wall thickness transitions to ensure wall ratios stay below recommended limits.",
        ]

        return AIManufacturingReviewReport(
            executive_summary=exec_summary,
            process_assumption=preset_name,
            selected_pull_direction=pull_dir_name,
            top_priorities=priorities,
            epistemic_provenance=report.epistemic_summary,
            general_tooling_guidelines=guidelines,
        )
