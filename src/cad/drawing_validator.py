"""Drawing Validator for TechDraw-generated FreeCAD documents.

Provides deterministic validation of a TechDraw drawing FCStd file:
- Document structure validation (objects, types)
- Page / template integrity
- View completeness and direction sanity
- Scale consistency
- Source object references
- Geometry non-emptiness
- File output existence
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import FreeCAD
import TechDraw


@dataclass
class ValidationIssue:
    """A single validation finding."""
    severity: str   # "error" | "warning" | "info"
    check: str      # name of the check that produced this
    message: str


@dataclass
class ValidationReport:
    """Complete validation result for a TechDraw drawing document."""
    document_path: str
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    # Extracted metadata
    page_name: Optional[str] = None
    template_path: Optional[str] = None
    template_width_mm: float = 0.0
    template_height_mm: float = 0.0
    projection_convention: Optional[str] = None
    views_found: List[str] = field(default_factory=list)
    source_object_label: Optional[str] = None
    effective_scale: float = 0.0

    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def summary_lines(self) -> List[str]:
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            "=" * 60,
            f"DRAWING VALIDATION — {status}",
            "=" * 60,
            f"  File                : {self.document_path}",
            f"  Page                : {self.page_name or 'N/A'}",
            f"  Template            : {Path(self.template_path).name if self.template_path else 'N/A'}",
            f"  Page Size           : {self.template_width_mm:.0f} × {self.template_height_mm:.0f} mm",
            f"  Projection          : {self.projection_convention or 'N/A'}",
            f"  Effective Scale     : {self.effective_scale:.4f}",
            f"  Views Found         : {', '.join(self.views_found)}",
            f"  Source Object       : {self.source_object_label or 'N/A'}",
            "",
            f"  Issues ({len(self.issues)} total, {len(self.errors())} errors, {len(self.warnings())} warnings):",
        ]
        for issue in self.issues:
            prefix = "  ✗" if issue.severity == "error" else "  ~" if issue.severity == "warning" else "  ℹ"
            lines.append(f"{prefix} [{issue.check}] {issue.message}")
        lines.append("=" * 60)
        return lines


class DrawingValidator:
    """Validates a TechDraw drawing FCStd document without requiring GUI."""

    REQUIRED_VIEWS = {"Front", "Top", "Left", "Right", "Bottom"}
    MIN_DIRECTION_MAGNITUDE = 1e-6

    def validate_file(self, fcstd_path: Path) -> ValidationReport:
        """Load a saved FCStd and validate all drawing invariants.

        Args:
            fcstd_path: Path to the .FCStd drawing file.

        Returns:
            ValidationReport with all findings.
        """
        fcstd_path = Path(fcstd_path).resolve()
        report = ValidationReport(
            document_path=str(fcstd_path),
            passed=False,
        )
        issues = report.issues

        # ── Check 1: File existence ──────────────────────────────────────────
        if not fcstd_path.exists():
            issues.append(ValidationIssue("error", "file_exists",
                f"FCStd file does not exist: {fcstd_path}"))
            return report

        if fcstd_path.stat().st_size == 0:
            issues.append(ValidationIssue("error", "file_size",
                "FCStd file is empty (0 bytes)."))
            return report

        issues.append(ValidationIssue("info", "file_exists",
            f"FCStd file exists: {fcstd_path.stat().st_size:,} bytes"))

        # ── Check 2: Document opens ──────────────────────────────────────────
        try:
            doc = FreeCAD.openDocument(str(fcstd_path))
        except Exception as e:
            issues.append(ValidationIssue("error", "document_open", str(e)))
            return report

        try:
            self._validate_document(doc, report)
        finally:
            FreeCAD.closeDocument(doc.Name)

        report.passed = not any(i.severity == "error" for i in issues)
        return report

    def validate_result(self, doc: FreeCAD.Document, report: ValidationReport) -> ValidationReport:
        """Validate a live (already open) FreeCAD document.

        Args:
            doc: Open FreeCAD document to validate.
            report: DrawingResult to fill.

        Returns:
            The report with findings appended.
        """
        self._validate_document(doc, report)
        report.passed = not any(i.severity == "error" for i in report.issues)
        return report

    # ─────────────────────────────────────────────────────────────────────────
    # Internal validators
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_document(self, doc: FreeCAD.Document, report: ValidationReport) -> None:
        issues = report.issues

        # ── Check 3: TechDraw page exists ────────────────────────────────────
        page = None
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawPage":
                page = o
                break

        if page is None:
            issues.append(ValidationIssue("error", "page_exists",
                "No TechDraw::DrawPage found in document."))
            return

        report.page_name = page.Name
        issues.append(ValidationIssue("info", "page_exists", f"DrawPage found: {page.Name}"))

        # ── Check 4: Template attached ───────────────────────────────────────
        tmpl = page.Template
        if tmpl is None:
            issues.append(ValidationIssue("error", "template_attached",
                "Page has no template attached."))
        else:
            tmpl_path_str = getattr(tmpl, "Template", "") or ""
            report.template_path = tmpl_path_str
            report.template_width_mm = float(tmpl.Width)
            report.template_height_mm = float(tmpl.Height)
            if not tmpl_path_str:
                issues.append(ValidationIssue("warning", "template_path",
                    "Template file path is empty."))
            else:
                issues.append(ValidationIssue("info", "template_attached",
                    f"Template: {Path(tmpl_path_str).name} "
                    f"({report.template_width_mm:.0f}×{report.template_height_mm:.0f} mm)"))

        # ── Check 5: Projection convention set ───────────────────────────────
        report.projection_convention = getattr(page, "ProjectionType", None)
        if report.projection_convention not in ("Third angle", "First angle"):
            issues.append(ValidationIssue("warning", "projection_convention",
                f"Unexpected ProjectionType: {report.projection_convention!r}"))
        else:
            issues.append(ValidationIssue("info", "projection_convention",
                f"Projection: {report.projection_convention}"))

        # ── Check 6: Projection group exists ─────────────────────────────────
        proj_group = None
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawProjGroup":
                proj_group = o
                break

        if proj_group is None:
            issues.append(ValidationIssue("error", "proj_group_exists",
                "No TechDraw::DrawProjGroup found in document."))
            return

        issues.append(ValidationIssue("info", "proj_group_exists",
            f"DrawProjGroup found: {proj_group.Name}"))

        # ── Check 7: Source object reference ─────────────────────────────────
        src_objs = getattr(proj_group, "Source", [])
        if not src_objs:
            issues.append(ValidationIssue("error", "source_reference",
                "ProjGroup.Source is empty — no geometry linked."))
        else:
            src = src_objs[0]
            report.source_object_label = src.Label
            issues.append(ValidationIssue("info", "source_reference",
                f"Source object: {src.Label} ({src.TypeId})"))

        # ── Check 8: Scale is positive ────────────────────────────────────────
        scale = float(proj_group.Scale)
        report.effective_scale = scale
        if scale <= 0:
            issues.append(ValidationIssue("error", "scale_positive",
                f"ProjGroup scale is non-positive: {scale}"))
        else:
            issues.append(ValidationIssue("info", "scale_positive",
                f"Effective scale: {scale:.4f}"))

        # ── Check 9: Required views exist ─────────────────────────────────────
        actual_views = {v.Label for v in proj_group.Views}
        report.views_found = sorted(list(actual_views))
        missing = self.REQUIRED_VIEWS - actual_views
        if missing:
            issues.append(ValidationIssue("error", "views_complete",
                f"Missing projection views: {sorted(missing)}"))
        else:
            issues.append(ValidationIssue("info", "views_complete",
                f"All 5 projection views present: {sorted(actual_views)}"))

        # ── Check 10: Each view has valid direction ───────────────────────────
        for v in proj_group.Views:
            d = v.Direction
            mag = (d.x ** 2 + d.y ** 2 + d.z ** 2) ** 0.5
            if mag < self.MIN_DIRECTION_MAGNITUDE:
                issues.append(ValidationIssue("error", "view_direction",
                    f"View '{v.Label}' has zero direction vector."))
            else:
                issues.append(ValidationIssue("info", "view_direction",
                    f"View '{v.Label}' direction: ({d.x:+.3f},{d.y:+.3f},{d.z:+.3f}) |mag|={mag:.4f}"))

        # ── Check 11: Each view has valid position ────────────────────────────
        for v in proj_group.Views:
            x, y = float(v.X), float(v.Y)
            # Views should be within reasonable page bounds (after group offset)
            pg_x = float(proj_group.X)
            pg_y = float(proj_group.Y)
            abs_x = pg_x + x
            abs_y = pg_y + y
            if report.template_width_mm > 0 and report.template_height_mm > 0:
                if not (-20 <= abs_x <= report.template_width_mm + 20):
                    issues.append(ValidationIssue("warning", "view_position",
                        f"View '{v.Label}' X={abs_x:.1f} may be outside page width {report.template_width_mm:.0f}mm"))
                if not (-20 <= abs_y <= report.template_height_mm + 20):
                    issues.append(ValidationIssue("warning", "view_position",
                        f"View '{v.Label}' Y={abs_y:.1f} may be outside page height {report.template_height_mm:.0f}mm"))

        # ── Check 12: Views have non-zero SVG output ─────────────────────────
        for v in proj_group.Views:
            try:
                svg = TechDraw.viewPartAsSvg(v)
                if len(svg) < 50:
                    issues.append(ValidationIssue("warning", "view_geometry",
                        f"View '{v.Label}' SVG output is suspiciously small ({len(svg)} chars)."))
                else:
                    issues.append(ValidationIssue("info", "view_geometry",
                        f"View '{v.Label}' SVG: {len(svg):,} chars"))
            except Exception as e:
                issues.append(ValidationIssue("warning", "view_geometry",
                    f"View '{v.Label}' SVG export error: {e}"))


def validate_drawing_file(fcstd_path: Path) -> ValidationReport:
    """Convenience function to validate a saved TechDraw FCStd file.

    Args:
        fcstd_path: Path to the .FCStd drawing document.

    Returns:
        ValidationReport with all findings.
    """
    validator = DrawingValidator()
    return validator.validate_file(fcstd_path)
