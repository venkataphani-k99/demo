"""Phase 26 Unit Tests: Injection Molding DFM, Draft Angle, Undercut & Slider Locating Engine."""
import numpy as np
from pathlib import Path

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.cad.mold_analyzer import MoldabilityAnalyzer, MoldabilityReport
from src.cad.slider_locator import SliderLocator, SliderAction


def create_test_box_with_side_hole():
    """Creates a stepped box with an undercut side through-hole requiring a side slider."""
    # Main block: 100 x 80 x 40
    box = Part.makeBox(100, 80, 40)
    # Side hole cutting through along X axis (undercut if pulled along Z)
    cylinder = Part.makeCylinder(8, 120, FreeCAD.Vector(-10, 40, 20), FreeCAD.Vector(1, 0, 0))
    shape = box.cut(cylinder)
    return shape


def test_moldability_analyzer_basic_classification():
    shape = create_test_box_with_side_hole()
    analyzer = MoldabilityAnalyzer(shape=shape, min_draft_deg=1.5)
    report = analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test_box")

    assert isinstance(report, MoldabilityReport)
    assert report.total_faces > 6
    # Top and bottom caps are correctly excluded as NOT_APPLICABLE_PLANAR_CAP
    # Outer sidewalls with zero draft are ZERO_DRAFT (applicable draw walls)
    assert len(report.applicable_faces) > 0, "Expected applicable draw faces"
    # The transverse cylinder bore is an undercut for +Z draw
    assert len(report.undercut_faces) > 0 or len(report.insufficient_draft_faces) > 0, "Expected undercut or draft deficiency"
    assert report.projected_area_mm2 > 0
    assert report.estimated_clamping_tonnage > 0
    assert report.moldability_score > 0
    assert len(report.direction_evaluations) >= 6



def test_slider_locator_detection():
    shape = create_test_box_with_side_hole()
    analyzer = MoldabilityAnalyzer(shape=shape, min_draft_deg=1.5)
    report = analyzer.analyze(custom_pull_direction=[0, 0, 1], project_id="test_box")

    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()

    # The cylinder hole has faces perpendicular to Z draw axis
    assert isinstance(sliders, list)
    for s in sliders:
        assert isinstance(s, SliderAction)
        assert len(s.pull_vector) == 3
        assert s.required_stroke_mm > 0
        assert len(s.source_faces) > 0
        assert s.recommended_cam_angle_deg >= 10.0


def test_mold_direction_evaluation_scoring():
    shape = Part.makeBox(50, 50, 50)
    analyzer = MoldabilityAnalyzer(shape=shape, min_draft_deg=1.0)
    
    # Clean cube: should identify +Z, -Z, +X, etc. with valid moldability scores
    report = analyzer.analyze(project_id="test_cube")
    assert report.optimal_direction_name is not None
    assert report.moldability_score >= 50.0
    assert len(report.tooling_recommendations) > 0
