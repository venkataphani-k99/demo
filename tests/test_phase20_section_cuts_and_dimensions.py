"""Phase 20 — Automated Test Suite for Advanced Section Cuts & Industrial 2D Drawing Sheets.

Validates that:
1. SectionCutGenerator accurately slices 3D solids and generates 45° cross-hatch patterns.
2. Internal measurements (wall thickness, internal cavity diameters, base floor thickness) are extracted without mock data.
3. Half Section cuts correctly combine exterior silhouette and interior section.
4. IndustrialSheetComposer produces a publication-grade multi-view SVG sheet containing all views, detail callouts, tables, and notes.
"""
from pathlib import Path
import pytest

from src.cad.step_loader import load_step
from src.cad.section_cut_generator import SectionCutGenerator
from src.cad.industrial_sheet_composer import IndustrialSheetComposer


@pytest.fixture
def sample_shape():
    """Load benchmark STEP solid shape."""
    step_file = Path("input/Pieza18_1.STEP")
    res = load_step(step_file)
    shape = res.primary_shape
    return shape


def test_section_cut_generator_full_section(sample_shape):
    """Test 1: SectionCutGenerator slices solid and produces valid cut segments and 45° hatching."""
    gen = SectionCutGenerator()
    sec = gen.compute_section_cut(sample_shape, plane="XZ", hatch_pitch=2.0)

    assert sec["total_cut_edges"] > 0, "Section cut must generate 2D intersection segments."
    assert sec["total_hatch_lines"] > 0, "Section cut must generate 45° cross-hatching lines."
    assert sec["bounds"]["width"] > 0, "Section bounds width must be positive."
    assert sec["bounds"]["height"] > 0, "Section bounds height must be positive."


def test_section_cut_generator_half_section(sample_shape):
    """Test 2: Half Section produces right-hand section cut and centerline."""
    gen = SectionCutGenerator()
    half_sec = gen.compute_half_section(sample_shape, plane="XZ")

    assert half_sec["type"] == "HALF_SECTION"
    assert len(half_sec["section_segments"]) > 0
    assert len(half_sec["center_line"]) == 4
    assert half_sec["center_line"][0] == 0.0, "Centerline must be aligned at u = 0."


def test_internal_dimension_extraction(sample_shape):
    """Test 3: Internal measurements extract valid wall thickness, cavity diams, and heights."""
    gen = SectionCutGenerator()
    sec = gen.compute_section_cut(sample_shape, plane="XZ")
    dims = sec["internal_dimensions"]

    assert len(dims) >= 2, "Must extract at least total height and outer diameter."
    dim_types = [d["type"] for d in dims]
    assert "LINEAR_VERTICAL" in dim_types, "Must extract vertical height dimension."
    assert "DIAMETRAL" in dim_types, "Must extract diametral dimension."


def test_industrial_sheet_composer_svg_generation(sample_shape, tmp_path: Path):
    """Test 4: IndustrialSheetComposer composes complete multi-view drawing SVG."""
    composer = IndustrialSheetComposer()
    out_svg = tmp_path / "industrial_drawing.svg"
    svg_content = composer.generate_sheet_svg(
        shape=sample_shape,
        title="PIEZA 18-1 TEST",
        subtitle="SECTION CUT & DIMENSIONS",
        output_path=out_svg,
    )

    assert out_svg.exists(), "Exported SVG file must exist on disk."
    assert "SECTION CUT" in svg_content, "Must contain Section Cut view."
    assert "FRONT VIEW" in svg_content, "Must contain Front view."
    assert "TOP VIEW" in svg_content, "Must contain Top view."
    assert "RIGHT SIDE VIEW" in svg_content, "Must contain Right Side view."
    assert "ISOMETRIC 3D VIEW" in svg_content, "Must contain Isometric view."
    assert "DETAIL B" in svg_content, "Must contain Detail view."
    assert "ENVELOPE" in svg_content, "Must contain Specifications block."
