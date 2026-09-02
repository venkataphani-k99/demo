"""Automated TechDraw Engineering Drawing Generator for FreeCAD 1.1.3.

This module implements a deterministic, scriptable TechDraw drawing pipeline:

    STEP file
      └─> FreeCAD B-Rep Document
            └─> TechDraw Page (ISO A3 Landscape, Third-Angle Projection)
                  ├─> DrawProjGroup
                  │     ├─> Front   (looking from -Y)
                  │     ├─> Top     (looking from +Z)
                  │     ├─> Left    (looking from -X)
                  │     ├─> Right   (looking from +X)
                  │     └─> Bottom  (looking from -Z)
                  └─> Template (ISO A3 Landscape blank)

Projection Convention: Third-Angle (ASME Y14.3 / ISO)
    In Third-Angle:
        - Front view is the primary view
        - Top view appears ABOVE front
        - Right view appears to the RIGHT of front
        - Left view appears to the LEFT of front
        - Bottom view appears BELOW front

APIs used (verified against FreeCAD 1.1.3):
    TechDraw::DrawPage          - page container
    TechDraw::DrawSVGTemplate   - ISO A3 SVG template
    TechDraw::DrawProjGroup     - orthographic projection group
    TechDraw::DrawProjGroupItem - individual projection (Front/Top/Left/Right/Bottom)
    TechDraw.viewPartAsSvg()    - per-view SVG export
    TechDraw.writeDXFPage()     - full page DXF export
    doc.saveAs()                - FreeCAD FCStd document persistence
"""
from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import FreeCAD
import Import
import TechDraw


# ─────────────────────────────────────────────────────────────────────────────
# Template Discovery
# ─────────────────────────────────────────────────────────────────────────────

# Priority-ordered list of template names to search for
PREFERRED_TEMPLATES = [
    "A3_Landscape_blank.svg",          # simplest, most portable
    "A3_Landscape_TD.svg",
    "A3_Landscape_ISO5457_minimal.svg",
    "A3_Landscape_ISO5457_notitleblock.svg",
    "A4_Landscape_blank.svg",
    "A4_Landscape_TD.svg",
]


def find_template_dir() -> Optional[Path]:
    """Locate the FreeCAD TechDraw template directory programmatically."""
    resource_dir = Path(FreeCAD.getResourceDir())
    candidates = [
        resource_dir / "data" / "Mod" / "TechDraw" / "Templates",
        resource_dir / "Mod" / "TechDraw" / "Templates",
        Path("C:/Program Files/FreeCAD 1.1/data/Mod/TechDraw/Templates"),
        Path("C:/Program Files/FreeCAD 1.0/data/Mod/TechDraw/Templates"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def find_template(preferred_name: Optional[str] = None) -> Path:
    """Locate a TechDraw SVG template file.

    Args:
        preferred_name: Filename of the preferred template (e.g. 'A3_Landscape_blank.svg').
                        If None, searches in priority order from PREFERRED_TEMPLATES.

    Returns:
        Absolute Path to the selected template SVG.

    Raises:
        FileNotFoundError: If no template can be found.
    """
    tmpl_dir = find_template_dir()
    if tmpl_dir is None:
        raise FileNotFoundError("Cannot locate FreeCAD TechDraw template directory.")

    search_names = [preferred_name] if preferred_name else PREFERRED_TEMPLATES

    for name in search_names:
        # Search ISO subdir first (most FreeCAD 1.x installs put them there)
        for candidate in [
            tmpl_dir / "ISO" / name,
            tmpl_dir / name,
        ]:
            if candidate.is_file():
                return candidate

    # Last resort: list all available templates and raise informative error
    available = []
    for root, _, files in os.walk(str(tmpl_dir)):
        for f in files:
            if f.endswith(".svg"):
                available.append(os.path.join(root, f))

    raise FileNotFoundError(
        f"Template not found. Available templates:\n" + "\n".join(available[:20])
    )


# ─────────────────────────────────────────────────────────────────────────────
# Drawing Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DrawingConfig:
    """Configuration for automated TechDraw drawing generation.

    Attributes:
        projection_convention: 'Third angle' (default, ASME/ISO) or 'First angle' (European).
        scale_type: 'Automatic' lets FreeCAD compute scale, 'Custom' uses scale_value.
        scale_value: Manual scale factor, e.g. 1.0 for 1:1, 0.5 for 1:2.
        views: Which standard orthographic views to include.
        template_name: Preferred template filename. None = auto-discover.
        spacing_x: Horizontal spacing between views in mm.
        spacing_y: Vertical spacing between views in mm.
        group_x: X-position of the projection group anchor on page in mm.
        group_y: Y-position of the projection group anchor on page in mm.
    """
    projection_convention: str = "Third angle"
    scale_type: str = "Automatic"           # "Automatic" or "Custom"
    scale_value: float = 1.0
    views: List[str] = field(default_factory=lambda: ["Front", "Top", "Left", "Right", "Bottom"])
    template_name: Optional[str] = "A3_Landscape_blank.svg"
    spacing_x: float = 25.0                 # mm between view columns
    spacing_y: float = 25.0                 # mm between view rows
    group_x: float = 150.0                  # mm — horizontal center of group on A3 page
    group_y: float = 130.0                  # mm — vertical center of group on A3 page


# ─────────────────────────────────────────────────────────────────────────────
# Drawing Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ViewInfo:
    """Metadata for a single generated TechDraw view."""
    name: str               # e.g. "Front"
    direction: List[float]  # 3D look-at direction vector [x, y, z]
    x: float                # page X position (mm)
    y: float                # page Y position (mm)
    scale: float
    svg_char_count: int     # 0 if not exported


@dataclass
class DrawingResult:
    """Result returned by generate_drawing()."""
    document_name: str
    step_file: str
    source_object_label: str
    template_path: str
    page_name: str
    projection_group_name: str
    projection_convention: str
    views: List[ViewInfo]
    fcstd_path: Optional[str] = None
    svg_path: Optional[str] = None
    dxf_path: Optional[str] = None
    scale_type: str = "Automatic"
    effective_scale: float = 1.0
    template_width_mm: float = 420.0
    template_height_mm: float = 297.0
    status: str = "ok"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def report_lines(self) -> List[str]:
        """Return a formatted human-readable summary."""
        lines = [
            "=" * 60,
            "TECHDRAW DRAWING GENERATION RESULT",
            "=" * 60,
            f"  Source STEP    : {self.step_file}",
            f"  Source Object  : {self.source_object_label}",
            f"  Template       : {Path(self.template_path).name}",
            f"  Page           : {self.page_name}",
            f"  Projection     : {self.projection_convention}",
            f"  Scale Type     : {self.scale_type}",
            f"  Effective Scale: {self.effective_scale:.4f}",
            f"  Page Size      : {self.template_width_mm:.0f} × {self.template_height_mm:.0f} mm",
            "",
            "  Views:",
        ]
        for v in self.views:
            d = v.direction
            lines.append(
                f"    {v.name:<8} dir=({d[0]:+.2f},{d[1]:+.2f},{d[2]:+.2f})"
                f"  x={v.x:7.2f}  y={v.y:7.2f}  scale={v.scale:.4f}"
            )
        lines += [
            "",
            f"  FCStd saved    : {self.fcstd_path or 'not saved'}",
            f"  SVG exported   : {self.svg_path or 'not exported'}",
            f"  DXF exported   : {self.dxf_path or 'not exported'}",
            f"  Status         : {self.status}",
        ]
        if self.errors:
            lines.append("  Errors:")
            for e in self.errors:
                lines.append(f"    ! {e}")
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append(f"    ~ {w}")
        lines.append("=" * 60)
        return lines


# ─────────────────────────────────────────────────────────────────────────────
# Drawing Generator
# ─────────────────────────────────────────────────────────────────────────────

class TechDrawGenerator:
    """Programmatic TechDraw drawing pipeline for FreeCAD 1.1.3.

    Usage:
        gen = TechDrawGenerator(config)
        result = gen.generate(
            step_path=Path('input/Pieza18_1.STEP'),
            output_dir=Path('output'),
        )
    """

    def __init__(self, config: Optional[DrawingConfig] = None):
        self.config = config or DrawingConfig()
        self._doc: Optional[FreeCAD.Document] = None
        self._page = None
        self._template = None
        self._proj_group = None
        self._src_obj = None

    def generate(
        self,
        step_path: Path,
        output_dir: Path,
        *,
        save_fcstd: bool = True,
        export_svg: bool = True,
        export_dxf: bool = True,
    ) -> DrawingResult:
        """Full drawing generation pipeline.

        Args:
            step_path: Path to the input STEP file.
            output_dir: Directory for output files.
            save_fcstd: Whether to save the FreeCAD document.
            export_svg: Whether to export an SVG of the drawing.
            export_dxf: Whether to export a DXF of the drawing.

        Returns:
            DrawingResult with all metadata and output paths.
        """
        step_path = Path(step_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = step_path.stem
        errors: List[str] = []
        warnings: List[str] = []

        # 6A — Load STEP
        self._doc, self._src_obj = self._load_step(step_path, errors)
        if self._src_obj is None:
            return DrawingResult(
                document_name="",
                step_file=str(step_path),
                source_object_label="",
                template_path="",
                page_name="",
                projection_group_name="",
                projection_convention=self.config.projection_convention,
                views=[],
                status="error",
                errors=errors,
            )

        # 6B — Create TechDraw page & template
        tmpl_path = find_template(self.config.template_name)
        self._template, self._page = self._create_page(tmpl_path)

        # 6C/6D — Create projection group with all views
        self._proj_group = self._create_projection_group()

        # 6G — Recompute and validate
        self._doc.recompute()
        validation_errors = self._validate()
        errors.extend(validation_errors)

        # Collect effective scale (Automatic uses a computed scale)
        effective_scale = self._compute_effective_scale()

        # Build view infos
        view_infos = self._collect_view_infos()

        # 6H — Save FCStd
        fcstd_path: Optional[str] = None
        if save_fcstd:
            fcstd_path = str(output_dir / f"{base_name}_drawing.FCStd")
            try:
                self._doc.saveAs(fcstd_path)
            except Exception as e:
                errors.append(f"FCStd save failed: {e}")
                fcstd_path = None

        # 6I — SVG export (composite multi-view SVG)
        svg_path: Optional[str] = None
        if export_svg:
            svg_path = str(output_dir / f"{base_name}_drawing.svg")
            try:
                self._export_svg_composite(svg_path)
            except Exception as e:
                warnings.append(f"SVG export failed: {e}")
                svg_path = None

        # 6I — DXF export
        dxf_path: Optional[str] = None
        if export_dxf:
            dxf_path = str(output_dir / f"{base_name}_drawing.dxf")
            try:
                TechDraw.writeDXFPage(self._page, dxf_path)
                if not Path(dxf_path).exists() or Path(dxf_path).stat().st_size == 0:
                    warnings.append("DXF export produced empty file.")
                    dxf_path = None
            except Exception as e:
                warnings.append(f"DXF export failed: {e}")
                dxf_path = None

        result = DrawingResult(
            document_name=self._doc.Name,
            step_file=str(step_path),
            source_object_label=self._src_obj.Label,
            template_path=str(tmpl_path),
            page_name=self._page.Name,
            projection_group_name=self._proj_group.Name,
            projection_convention=self.config.projection_convention,
            views=view_infos,
            fcstd_path=fcstd_path,
            svg_path=svg_path,
            dxf_path=dxf_path,
            scale_type=self.config.scale_type,
            effective_scale=effective_scale,
            template_width_mm=float(self._template.Width),
            template_height_mm=float(self._template.Height),
            status="ok" if not errors else "error",
            errors=errors,
            warnings=warnings,
        )

        return result

    def close(self) -> None:
        """Close the underlying FreeCAD document."""
        if self._doc is not None:
            try:
                FreeCAD.closeDocument(self._doc.Name)
            except Exception:
                pass
            self._doc = None

    # ─────────────────────────────────────────────────────────────────────
    # Internal pipeline steps
    # ─────────────────────────────────────────────────────────────────────

    def _load_step(
        self, step_path: Path, errors: List[str]
    ) -> Tuple[Optional[FreeCAD.Document], Optional[object]]:
        """6A: Load STEP file into a fresh FreeCAD document."""
        if not step_path.exists():
            errors.append(f"STEP file not found: {step_path}")
            return None, None
        if step_path.suffix.lower() not in (".step", ".stp"):
            errors.append(f"Not a STEP file: {step_path}")
            return None, None

        doc_name = f"TechDraw_{step_path.stem}"
        doc = FreeCAD.newDocument(doc_name)
        Import.insert(str(step_path), doc.Name)
        doc.recompute()

        # Identify solid source objects (support single part or multi-part assembly)
        solid_objs = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull() and len(o.Shape.Solids) >= 1]
        if not solid_objs:
            solid_objs = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]

        if len(solid_objs) == 1:
            src_obj = solid_objs[0]
        elif len(solid_objs) > 1:
            # Multi-solid assembly: create compound feature
            cmp = doc.addObject("Part::Compound", "AssemblyCompound")
            cmp.Links = solid_objs
            doc.recompute()
            src_obj = cmp
        else:
            errors.append("No solid B-Rep object found in imported STEP document.")
            FreeCAD.closeDocument(doc.Name)
            return None, None

        # Validate bounding box is available
        bb = src_obj.Shape.BoundBox
        if bb.XLength <= 0 or bb.YLength <= 0 or bb.ZLength <= 0:
            errors.append("Source shape bounding box is degenerate (zero dimension).")

        return doc, src_obj

    def _create_page(self, tmpl_path: Path) -> Tuple[object, object]:
        """6B: Create TechDraw page with SVG template."""
        tmpl = self._doc.addObject("TechDraw::DrawSVGTemplate", "Template")
        tmpl.Template = str(tmpl_path)

        page = self._doc.addObject("TechDraw::DrawPage", "DrawingPage")
        page.Template = tmpl
        page.ProjectionType = self.config.projection_convention

        return tmpl, page

    def _create_projection_group(self) -> object:
        """6C/6D: Create orthographic projection group with optimized fast HLR projection."""
        pg = self._doc.addObject("TechDraw::DrawProjGroup", "ProjGroup")
        pg.Source = [self._src_obj]
        pg.ProjectionType = self.config.projection_convention

        # Configure scale
        if self.config.scale_type == "Automatic":
            pg.ScaleType = "Automatic"
        else:
            pg.ScaleType = "Custom"
            pg.Scale = self.config.scale_value

        # Inter-view spacing
        pg.spacingX = self.config.spacing_x
        pg.spacingY = self.config.spacing_y

        # Always add Front first — it becomes the anchor
        # For massive assemblies (> 5k edges), adaptively restrict view count to avoid quadratic CPU freeze
        num_edges = len(self._src_obj.Shape.Edges) if hasattr(self._src_obj, "Shape") else 0
        views_to_add = self.config.views
        if num_edges > 5000:
            views_to_add = [v for v in self.config.views if v in ("Front", "Top", "Isometric")][:2]

        front_item = pg.addProjection("Front")
        for prop in ["HardHidden", "SmoothHidden", "SmoothVisible", "SeamVisible", "IsoCount", "CoarseView"]:
            try:
                if prop in ["HardHidden", "SmoothHidden"]:
                    setattr(front_item, prop, False)
                elif prop in ["SmoothVisible", "SeamVisible"]:
                    if num_edges > 3000:
                        setattr(front_item, prop, False)
                elif prop == "IsoCount":
                    setattr(front_item, prop, 0)
                elif prop == "CoarseView":
                    setattr(front_item, prop, True)
            except Exception:
                pass

        # Add remaining views
        for view_name in views_to_add:
            if view_name == "Front":
                continue  # already added
            item = pg.addProjection(view_name)
            for prop in ["HardHidden", "SmoothHidden", "SmoothVisible", "SeamVisible", "IsoCount", "CoarseView"]:
                try:
                    if prop in ["HardHidden", "SmoothHidden"]:
                        setattr(item, prop, False)
                    elif prop in ["SmoothVisible", "SeamVisible"]:
                        if num_edges > 3000:
                            setattr(item, prop, False)
                    elif prop == "IsoCount":
                        setattr(item, prop, 0)
                    elif prop == "CoarseView":
                        setattr(item, prop, True)
                except Exception:
                    pass

        # Set anchor (Front view drives the coordinate origin for AutoDistribute)
        pg.Anchor = front_item

        # 6E: Place the group on the page
        pg.X = self.config.group_x
        pg.Y = self.config.group_y

        self._page.addView(pg)

        return pg

    def _validate(self) -> List[str]:
        """6G: Validate document state after recompute."""
        errors: List[str] = []

        # Page exists
        if self._page is None:
            errors.append("TechDraw page was not created.")
            return errors

        # Template attached
        if self._page.Template is None:
            errors.append("TechDraw page has no template.")

        # Projection group has correct number of views
        expected = set(self.config.views)
        actual = {v.Label for v in self._proj_group.Views}
        missing = expected - actual
        if missing:
            errors.append(f"Missing projection views: {missing}")

        # Each view has valid direction (non-zero)
        for v in self._proj_group.Views:
            d = v.Direction
            mag = (d.x ** 2 + d.y ** 2 + d.z ** 2) ** 0.5
            if mag < 1e-6:
                errors.append(f"View '{v.Label}' has zero direction vector.")

        # Proj group source is set
        if not self._proj_group.Source:
            errors.append("Projection group has no source object.")

        # Scale is non-zero
        s = float(self._proj_group.Scale)
        if s <= 0:
            errors.append(f"Projection group scale is non-positive: {s}")

        return errors

    def _compute_effective_scale(self) -> float:
        """Extract the actual computed scale from the projection group."""
        try:
            return float(self._proj_group.Scale)
        except Exception:
            return self.config.scale_value

    def _collect_view_infos(self) -> List[ViewInfo]:
        """Collect position / direction metadata for every view without redundant SVG rendering."""
        infos: List[ViewInfo] = []
        for v in self._proj_group.Views:
            d = v.Direction
            infos.append(
                ViewInfo(
                    name=v.Label,
                    direction=[float(d.x), float(d.y), float(d.z)],
                    x=float(v.X),
                    y=float(v.Y),
                    scale=float(v.Scale),
                    svg_char_count=0,
                )
            )
        return infos

    def _export_svg_composite(self, svg_path: str) -> None:
        """6I: Compose a multi-view SVG from all projection views.

        FreeCAD 1.1.3 does not expose a direct page-to-SVG API in headless mode.
        We assemble a composite SVG by:
          1. Loading the blank template SVG as the background.
          2. Placing each view's SVG geometry at the correct page coordinate.

        Page coordinates (FreeCAD TechDraw convention):
          - Origin is bottom-left of template
          - Y increases upward
          - SVG coordinate origin is top-left, Y increases downward
          => y_svg = page_height - y_td
        """
        page_w = float(self._template.Width)
        page_h = float(self._template.Height)

        # SVG header
        svg_parts = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg"',
            f'     xmlns:xlink="http://www.w3.org/1999/xlink"',
            f'     width="{page_w}mm" height="{page_h}mm"',
            f'     viewBox="0 0 {page_w} {page_h}">',
            f'  <title>TechDraw Drawing — {self._src_obj.Label}</title>',
            # White page background
            f'  <rect width="{page_w}" height="{page_h}" fill="white" stroke="#cccccc" stroke-width="0.5"/>',
            # Page border
            f'  <rect x="5" y="5" width="{page_w-10}" height="{page_h-10}" fill="none"'
            f' stroke="#333333" stroke-width="0.7"/>',
        ]

        # Projection group offset: pg.X / pg.Y is anchor (Front) center in TechDraw coords
        pg_x = float(self._proj_group.X)
        pg_y = float(self._proj_group.Y)

        # Helper: TechDraw page coord → SVG coord
        def td_to_svg(td_x: float, td_y: float) -> Tuple[float, float]:
            return td_x, page_h - td_y

        for v in self._proj_group.Views:
            view_td_x = pg_x + float(v.X)
            view_td_y = pg_y + float(v.Y)
            svg_x, svg_y = td_to_svg(view_td_x, view_td_y)

            try:
                view_svg = TechDraw.viewPartAsSvg(v)
                # Strip the outer <svg> wrapper to get just the geometry elements
                inner = _extract_svg_inner(view_svg)
            except Exception:
                inner = ""

            # Wrap in a translated group
            # TechDraw SVG has geometry centred at (0,0); translate to view position
            svg_parts.append(
                f'  <g id="view_{v.Label}" transform="translate({svg_x:.4f},{svg_y:.4f})">'
            )
            if inner:
                svg_parts.append(inner)
            else:
                # Placeholder if geometry was empty
                svg_parts.append(
                    f'    <text x="0" y="0" font-size="3" fill="#999">[{v.Label}]</text>'
                )
            svg_parts.append(f'  </g>')

            # View label
            label_x = svg_x
            label_y = svg_y + 8  # slightly below the view centre in SVG coords
            d = v.Direction
            svg_parts.append(
                f'  <text x="{label_x:.2f}" y="{label_y:.2f}"'
                f' text-anchor="middle" font-family="sans-serif"'
                f' font-size="4" fill="#444">{v.Label}</text>'
            )

        svg_parts.append("</svg>")
        svg_content = "\n".join(svg_parts)

        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)


def _extract_svg_inner(svg_str: str) -> str:
    """Extract geometry content from inside an <svg>...</svg> wrapper."""
    # Simple, dependency-free extraction without a full XML parser
    lower = svg_str.lower()
    start_tag_end = lower.find(">")
    end_tag_start = lower.rfind("</svg>")
    if start_tag_end == -1 or end_tag_start == -1:
        return svg_str  # return as-is if can't parse
    return svg_str[start_tag_end + 1 : end_tag_start].strip()


# ─────────────────────────────────────────────────────────────────────────────
# Public convenience function
# ─────────────────────────────────────────────────────────────────────────────

def generate_drawing(
    step_path: Path,
    output_dir: Path,
    config: Optional[DrawingConfig] = None,
    *,
    save_fcstd: bool = True,
    export_svg: bool = True,
    export_dxf: bool = True,
) -> DrawingResult:
    """Generate a TechDraw drawing from a STEP file.

    This is the main entry point for the CLI and test suite.

    Args:
        step_path: Path to the input STEP file.
        output_dir: Output directory for all generated artefacts.
        config: Drawing configuration. Uses default A3 landscape if None.
        save_fcstd: Save .FCStd drawing document.
        export_svg: Export composite multi-view SVG.
        export_dxf: Export DXF via TechDraw.writeDXFPage().

    Returns:
        DrawingResult with all paths and metadata.
    """
    gen = TechDrawGenerator(config)
    try:
        result = gen.generate(
            step_path=step_path,
            output_dir=output_dir,
            save_fcstd=save_fcstd,
            export_svg=export_svg,
            export_dxf=export_dxf,
        )
    finally:
        gen.close()
    return result
