"""CAD Intelligence CLI Entrypoint.

Usage:
    python -m src.main input/Pieza18_1.STEP
    python -m src.main input/Pieza18_1.STEP --output-dir custom_output/

    python -m src.main draw input/Pieza18_1.STEP
    python -m src.main draw input/Pieza18_1.STEP --output-dir custom_output/
    python -m src.main draw input/Pieza18_1.STEP --projection third --scale 1.0

    python -m src.main dimensions input/Pieza18_1.STEP
    python -m src.main dimensions input/Pieza18_1.STEP --output-dir custom_output/

    python -m src.main dimension-drawing input/Pieza18_1.STEP
    python -m src.main dimension-drawing input/Pieza18_1.STEP --output-dir custom_output/

    python -m src.main complete-dimensions input/Pieza18_1.STEP
    python -m src.main complete-dimensions input/Pieza18_1.STEP --output-dir custom_output/
    python -m src.main reconstruct output/Pieza18_1_complete_dimensioned.svg
    python -m src.main reconstruct output/Pieza18_1_complete_dimensioned.svg --partial-mode
    python -m src.main reconstruct output/drawing.png --workspace-dir ./workspaces
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401

try:
    import FreeCAD  # noqa: F401
    _FREECAD_AVAILABLE = True
except ImportError:
    _FREECAD_AVAILABLE = False

# Lazy imports — FreeCAD is not required for all subcommands
load_step = None
analyze_cad_model = None
export_analysis_reports = None
CadImportError = Exception


def _import_cad_modules():
    global load_step, analyze_cad_model, export_analysis_reports, CadImportError
    if load_step is None:
        from src.cad.step_loader import load_step as _ls, CadImportError as _CIE
        from src.analysis.analyzer import analyze_cad_model as _acm
        from src.analysis.report import export_analysis_reports as _ear
        load_step = _ls
        analyze_cad_model = _acm
        export_analysis_reports = _ear
        CadImportError = _CIE


def run_pipeline(step_path: Path, output_dir: Path) -> int:
    """Execute complete STEP loading, B-Rep analysis, and reporting pipeline."""
    _import_cad_modules()
    print("=" * 60)
    print("CAD INTELLIGENCE — STEP INSPECTION PIPELINE")
    print("=" * 60)
    print(f"Target File : {step_path.name}")
    print(f"Path        : {step_path}")
    print("-" * 60)

    load_result = None
    try:
        # 1. Load STEP file
        print("[1/3] Loading and validating STEP model via FreeCAD...")
        load_result = load_step(step_path)
        print(f"      Successfully loaded: {load_result.file_name}")
        print(f"      STEP Schema: {load_result.metadata.schema}")
        print(f"      Detected Units: {load_result.metadata.units}")

        # 2. Analyze B-Rep geometry and topology
        print("[2/3] Extracting deterministic B-Rep geometry & topology...")
        analysis = analyze_cad_model(load_result)
        bbox = analysis.bounding_box
        print(f"      Solids: {analysis.topology.solids} | Faces: {analysis.topology.faces} | Edges: {analysis.topology.edges} | Vertices: {analysis.topology.vertices}")
        print(f"      Bounding Box Size: {bbox.length_x:.3f} × {bbox.length_y:.3f} × {bbox.length_z:.3f} {analysis.units}")

        # 3. Export Reports & 3D Mesh
        print("[3/3] Exporting analysis, features, and 3D mesh artifacts...")
        json_path, txt_path, feat_json_path, feat_txt_path = export_analysis_reports(analysis, output_dir)
        try:
            from src.cad.mesh_exporter import export_mesh_from_shape
            mesh_json_path = output_dir / f"{step_path.stem}_mesh.json"
            export_mesh_from_shape(load_result.primary_shape or load_result.shape, mesh_json_path)
            print(f"      3D Mesh       (JSON): {mesh_json_path}")
        except Exception as mesh_exc:
            print(f"      [WARN] 3D mesh export non-blocking: {mesh_exc}")
        print(f"      Full Analysis (JSON): {json_path}")
        print(f"      Full Report   (TXT) : {txt_path}")
        print(f"      Features List (JSON): {feat_json_path}")
        print(f"      Features Text (TXT) : {feat_txt_path}")
        print("=" * 60)
        print(f"STEP FEATURE RECOGNITION COMPLETED: {len(analysis.features)} FEATURES CONFIRMED.")
        print("=" * 60)
        return 0

    except CadImportError as e:
        print(f"\n[ERROR] CAD Import Error: {str(e)}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"\n[ERROR] File Not Found: {str(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected Error during CAD inspection: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if load_result:
            load_result.close()


def run_draw_pipeline(
    step_path: Path,
    output_dir: Path,
    projection: str = "third",
    scale: float = 0.0,
) -> int:
    """Execute automated TechDraw drawing generation pipeline (Phase 6)."""
    from src.cad.techdraw_generator import DrawingConfig, generate_drawing
    from src.cad.drawing_validator import validate_drawing_file

    convention = "Third angle" if projection.lower() in ("third", "3rd", "third angle") else "First angle"
    scale_type = "Automatic" if scale <= 0.0 else "Custom"
    scale_val = scale if scale > 0.0 else 1.0

    print("=" * 60)
    print("CAD INTELLIGENCE — AUTOMATED DRAWING GENERATOR")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print(f"Projection  : {convention}")
    print(f"Scale       : {'Automatic' if scale_type == 'Automatic' else str(scale_val)}")
    print("-" * 60)

    config = DrawingConfig(
        projection_convention=convention,
        scale_type=scale_type,
        scale_value=scale_val,
        views=["Front", "Top", "Left", "Right", "Bottom"],
        template_name="A3_Landscape_blank.svg",
        spacing_x=25.0,
        spacing_y=25.0,
        group_x=150.0,
        group_y=130.0,
    )

    try:
        print("Loading STEP...", end="  ")
        result = generate_drawing(
            step_path=step_path,
            output_dir=output_dir,
            config=config,
            save_fcstd=True,
            export_svg=True,
            export_dxf=True,
        )
        print("OK")

        if result.status == "error":
            for err in result.errors:
                print(f"  [ERROR] {err}", file=sys.stderr)
            return 1

        print(f"Creating TechDraw page... ", end=" ")
        print("OK")
        print(f"Creating projection group...", end=" ")
        print("OK")
        print()
        print("Views:")
        for v in result.views:
            d = v.direction
            dir_str = f"({d[0]:+.2f},{d[1]:+.2f},{d[2]:+.2f})"
            print(f"    {v.name:<8} direction={dir_str}  x={v.x:7.2f}mm  y={v.y:7.2f}mm")
        print()
        print(f"  Template    : {Path(result.template_path).name}")
        print(f"  Page Size   : {result.template_width_mm:.0f} × {result.template_height_mm:.0f} mm")
        print(f"  Scale       : {result.effective_scale:.4f}  (type={result.scale_type})")
        print()

        if result.fcstd_path:
            print(f"Saving:  {result.fcstd_path}")
            print("                         OK")
        if result.svg_path:
            print(f"SVG:     {result.svg_path}")
            print("                         OK")
        if result.dxf_path:
            print(f"DXF:     {result.dxf_path}")
            print("                         OK")

        if result.warnings:
            print()
            for w in result.warnings:
                print(f"  [WARNING] {w}")

        # Validate saved FCStd
        if result.fcstd_path:
            print()
            print("Validating saved FCStd...")
            val_report = validate_drawing_file(Path(result.fcstd_path))
            for line in val_report.summary_lines():
                print(line)
            if not val_report.passed:
                return 1

        print()
        print("=" * 60)
        print("AUTOMATED DRAWING GENERATION COMPLETE")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[ERROR] Drawing generation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_dimensions_pipeline(step_path: Path, output_dir: Path) -> int:
    """Execute Phase 7 dimension candidate generation + view visibility analysis."""
    from src.cad.step_loader import CadImportError, load_step
    from src.cad.topology import build_topology_graph
    from src.cad.measurements import MeasurementEngine
    from src.cad.features import recognize_cad_features
    from src.cad.dimensions import DimensionCandidateEngine
    from src.cad.view_analysis import analyse_view_visibility
    from src.analysis.report import export_dimension_reports

    print("=" * 60)
    print("CAD INTELLIGENCE — DIMENSION CANDIDATE ANALYSIS")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print("-" * 60)

    load_result = None
    try:
        print("Extracting geometry...", end="  ")
        load_result = load_step(step_path)
        shape = load_result.primary_shape
        print("OK")

        topo = build_topology_graph(shape)
        engine = MeasurementEngine(shape)

        print("Loading recognized features...", end="  ")
        features = recognize_cad_features(shape, topo, engine)
        print("OK")

        print("Generating dimension candidates...", end="  ")
        dim_engine = DimensionCandidateEngine(
            features=features,
            engine=engine,
            topo_graph=topo,
            model_file=step_path.name,
        )
        candidate_set = dim_engine.generate()
        print("OK")

        print()
        print(f"Candidates generated  : {candidate_set.total}")
        print(f"Valid                 : {candidate_set.valid}")
        print(f"Ambiguous             : {candidate_set.ambiguous}")
        print(f"Rejected              : {candidate_set.rejected}")
        print()

        print("Running view visibility analysis...", end="  ")
        view_report = analyse_view_visibility(candidate_set)
        print("OK")

        base_name = step_path.stem
        json_path, txt_path = export_dimension_reports(
            candidate_set, view_report, output_dir, base_name
        )
        print()
        print(f"Writing: {json_path}")
        print(f"Writing: {txt_path}")
        print()
        print("=" * 60)
        print("DIMENSION CANDIDATE ANALYSIS COMPLETE")
        print("=" * 60)
        return 0

    except CadImportError as e:
        print(f"\n[ERROR] CAD Import Error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"\n[ERROR] File Not Found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if load_result:
            load_result.close()


def run_dimensioned_drawing_pipeline(step_path: Path, output_dir: Path) -> int:
    """Execute Phase 8 dimension placement on TechDraw drawing."""
    from src.cad.dimension_placement import generate_dimensioned_drawing

    print("=" * 60)
    print("CAD INTELLIGENCE — TECHDRAW DIMENSION PLACEMENT PIPELINE")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print("-" * 60)

    try:
        print("Executing dimension placement pipeline...", end="  ")
        plan, fcstd_path, json_path, txt_path = generate_dimensioned_drawing(
            step_path=step_path,
            output_dir=output_dir,
        )
        print("OK")
        print()
        print(f"Total Candidates : {plan.total_candidates}")
        print(f"Placed           : {plan.placed_count}")
        print(f"Excluded         : {plan.excluded_count}")
        print(f"Failed           : {plan.failed_count}")
        print()
        print("Placed Dimensions:")
        for item in plan.items:
            if item.placement_status == "placed":
                val_sym = "✓" if item.validation_status == "passed" else "✗"
                print(f"  [{val_sym}] {item.dimension_id:<5} {item.formatted_value:<12} on {item.selected_view:<6} at ({item.x_mm:.1f}, {item.y_mm:.1f}) mm (Val: {item.validation_status})")
        print()
        print(f"Drawing saved : {fcstd_path}")
        print(f"Plan (JSON)   : {json_path}")
        print(f"Report (TXT)  : {txt_path}")
        print()
        print("=" * 60)
        print("TECHDRAW DIMENSION PLACEMENT COMPLETE")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[ERROR] Dimension placement failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_complete_dimensioned_drawing_pipeline(step_path: Path, output_dir: Path) -> int:
    """Execute Phase 9A complete deterministic dimensioning on TechDraw drawing."""
    from src.cad.complete_dimensioning import generate_complete_dimensioned_drawing

    print("=" * 60)
    print("CAD INTELLIGENCE — COMPLETE ENGINEERING DIMENSIONING")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print("-" * 60)

    try:
        print("Executing complete dimensioning pipeline...", end="  ")
        plan, fcstd_path, json_path, txt_path = generate_complete_dimensioned_drawing(
            step_path=step_path,
            output_dir=output_dir,
        )
        print("OK")
        print()
        print(f"Total Candidates : {plan.total_candidates}")
        print(f"Placed on Sheet  : {plan.placed_count}")
        print(f"Excluded/Deferred: {plan.excluded_count}")
        print(f"Placement Failed : {plan.failed_count}")
        print(f"Independent Dims : {plan.independent_count}")
        print(f"Derived Dims     : {plan.derived_count}")
        print(f"Geometric Rel/Ang: {plan.constraint_count}")
        print(f"Ambiguous Dims   : {plan.ambiguous_count}")
        print()
        print("Placed Dimensions:")
        for item in plan.items:
            if item.placement_status == "placed":
                val_sym = "✓" if item.validation_status == "passed" else "✗"
                print(f"  [{val_sym}] {item.dimension_id:<5} {item.display_value:<12} on {item.selected_view:<6} at ({item.x_mm:.1f}, {item.y_mm:.1f}) mm (Val: {item.validation_status})")
        print()
        print(f"Drawing saved : {fcstd_path}")
        print(f"Plan (JSON)   : {json_path}")
        print(f"Report (TXT)  : {txt_path}")
        print()
        print("=" * 60)
        print("COMPLETE ENGINEERING DIMENSIONING COMPLETE")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[ERROR] Complete dimensioning failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_ai_review_pipeline(
    step_path: Path,
    output_dir: Path,
    provider_name: str = "mock",
) -> int:
    """Execute live engineering intelligence review pipeline (Phase 11)."""
    from src.intelligence.providers import get_reasoning_provider
    from src.intelligence.review_engine import EngineeringReviewEngine

    print("=" * 60)
    print("CAD INTELLIGENCE — MULTIMODAL ENGINEERING REVIEW")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print(f"Provider    : {provider_name}")
    print("-" * 60)

    try:
        provider = get_reasoning_provider(provider_name)
        engine = EngineeringReviewEngine(provider=provider)
        review, json_path, txt_path = engine.run_review(step_path, output_dir)

        print(f"Review ID           : {review.review_id}")
        print(f"Overall Assessment  : {review.overall_assessment.upper()}")
        print(f"Requires Review     : {review.requires_human_review}")
        print(f"Recommendations     : {len(review.recommendations)}")
        print(f"Gatekeeper Rejections: {review.stats.get('gatekeeper_rejected_recommendations', 0)}")
        print()
        print(f"Review (JSON)       : {json_path}")
        print(f"Review (TXT)        : {txt_path}")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[ERROR] Engineering review failed: {e}", file=sys.stderr)
        return 1


def run_engineering_review_pipeline(step_path: Path, output_dir: Path) -> int:
    """Execute Phase 12 Engineering Issue & Recommendation Engine."""
    from src.intelligence.issue_engine import EngineeringIssueEngine

    print("=" * 60)
    print("CAD INTELLIGENCE — ENGINEERING ISSUE & RECOMMENDATION REVIEW")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print("-" * 60)

    try:
        engine = EngineeringIssueEngine(step_path, output_dir)
        summary = engine.process_visual_reviews()

        base_name = step_path.stem
        print(f"Total Issues Validated   : {len(engine.issues)}")
        print(f"Consensus Issues         : {summary.get('consensus', {}).get('consensus_issues_count', 0)}")
        print(f"Recommendations Generated: {len(engine.recommendations)}")
        print(f"Human Approval Boundary  : AWAITING_HUMAN_APPROVAL (Zero CAD Mutation)")
        print()
        print(f"Issues JSON        : {output_dir / f'{base_name}_engineering_issues.json'}")
        print(f"Recommendations    : {output_dir / f'{base_name}_engineering_recommendations.json'}")
        print(f"Summary JSON       : {output_dir / f'{base_name}_engineering_review_summary.json'}")
        print(f"Review Report (TXT): {output_dir / f'{base_name}_engineering_review.txt'}")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[ERROR] Engineering review engine failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_reconstruction_pipeline(
    drawing_path: Path,
    workspace_root: Path = Path("workspaces"),
    partial_mode: bool = True,
) -> int:
    """Execute the 2D drawing → 3D CAD reconstruction pipeline (Phase 17–19B)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from src.drawing.pipeline import ReconstructionPipeline

    pipeline = ReconstructionPipeline(
        workspace_root=workspace_root,
        partial_mode=partial_mode,
    )

    try:
        result = pipeline.run(drawing_path)
    except FileNotFoundError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\n[ERROR] Pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Print summary
    print("=" * 60)
    print("2D → 3D RECONSTRUCTION COMPLETE")
    print("=" * 60)
    print(f"Success           : {result['success']}")
    print(f"Project ID        : {result['project_id']}")
    print(f"Workspace         : {result['workspace_path']}")
    print(f"Elapsed           : {result['elapsed_seconds']}s")
    print(f"Analysis errors   : {result['analysis_errors']}")
    print()
    print("Analysis:")
    print(f"  Claude dims     : {result['analysis']['claude_dimensions']}")
    print(f"  Gemini dims     : {result['analysis']['gemini_dimensions']}")
    print(f"  Consensus agreed: {result['analysis']['consensus_agreed']}")
    print(f"  Features found  : {result['analysis']['features_synthesized']}")
    print()
    print("Reconstruction Plan:")
    print(f"  Status          : {result['plan']['status']}")
    print(f"  Steps           : {result['plan']['steps']}")
    print(f"  Gate 19B        : {result['plan']['gate_19b']}")
    print(f"  Rationale       : {result['plan']['gate_rationale']}")
    print()
    print("Execution:")
    print(f"  Success         : {result['execution']['success']}")
    print(f"  Gate status     : {result['execution']['gate_status']}")
    print(f"  Executable steps: {result['execution']['executable']}")
    print(f"  Partial steps   : {result['execution']['partial']}")
    print(f"  Skipped steps   : {result['execution']['skipped']}")
    print(f"  Failed steps    : {result['execution']['failed']}")
    if result['execution']['error']:
        print(f"  Error           : {result['execution']['error']}")
    print("=" * 60)

    return 0 if result["success"] else 1


def run_mold_analysis_pipeline(
    step_path: Path,
    output_dir: Path,
    min_draft: float = 1.5,
) -> int:
    """Execute Phase 26 Injection Molding & Slider DFM analysis pipeline."""
    from src.cad.step_loader import load_step
    from src.cad.mold_analyzer import MoldabilityAnalyzer
    from src.cad.slider_locator import SliderLocator

    print("=" * 60)
    print("CAD INTELLIGENCE — INJECTION MOLDING & DFM ANALYSIS")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print(f"Min Draft   : {min_draft}°")
    print("-" * 60)

    loaded = None
    try:
        loaded = load_step(step_path)
        shape = loaded.primary_shape or loaded.shape
        analyzer = MoldabilityAnalyzer(shape=shape, min_draft_deg=min_draft)
        report = analyzer.analyze(project_id=step_path.stem)

        locator = SliderLocator(shape=shape, mold_report=report)
        sliders = locator.locate_sliders()

        report_dict = report.to_dict()
        report_dict["sliders"] = [s.to_dict() for s in sliders]

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{step_path.stem}_mold_analysis.json"
        json_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

        print(f"Optimal Pull Axis    : {report.optimal_direction_name}")
        print(f"Cavity Faces         : {len(report.cavity_faces)}")
        print(f"Core Faces           : {len(report.core_faces)}")
        print(f"Insufficient Draft   : {len(report.insufficient_draft_faces)} faces")
        print(f"Undercut Faces       : {len(report.undercut_faces)} faces ({report.undercut_area_mm2:.1f} mm²)")
        print(f"Side-Action Sliders  : {len(sliders)} required")
        print(f"Clamping Requirement : {report.estimated_clamping_tonnage:.0f} Tonnes")
        print(f"Moldability Score    : {report.moldability_score:.1f} / 100")
        print(f"Artifact Saved       : {json_path}")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[ERROR] Mold analysis failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if loaded:
            loaded.close()


def run_mfg_review_pipeline(
    step_path: Path,
    output_dir: Path,
    preset_id: str = "GENERAL_PLASTIC_INJECTION",
) -> int:
    """Execute Phase M1 Manufacturing Intelligence & Moldability Review pipeline."""
    from src.cad.step_loader import load_step
    from src.cad.mold_analyzer import MoldabilityAnalyzer
    from src.cad.slider_locator import SliderLocator
    from src.cad.ai_manufacturing_reviewer import AIManufacturingReviewer

    print("=" * 60)
    print("CAD INTELLIGENCE — PHASE M1 MANUFACTURING REVIEW")
    print("=" * 60)
    print(f"Input       : {step_path.name}")
    print(f"Path        : {step_path}")
    print(f"Preset      : {preset_id}")
    print("-" * 60)

    loaded = None
    try:
        loaded = load_step(step_path)
        shape = loaded.primary_shape or loaded.shape
        analyzer = MoldabilityAnalyzer(shape=shape, process_preset_id=preset_id)
        report = analyzer.analyze(project_id=step_path.stem)

        locator = SliderLocator(shape=shape, mold_report=report)
        sliders = locator.locate_sliders()
        ai_report = AIManufacturingReviewer.generate_review(report)

        report_dict = report.to_dict()
        report_dict["sliders"] = [s.to_dict() for s in sliders]
        report_dict["ai_review"] = ai_report.to_dict()

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{step_path.stem}_{preset_id}_mfg_review.json"
        json_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

        print(f"Preferred Pull Axis  : {report.optimal_direction_name}")
        print(f"Candidate Directions : {len(report.pull_direction_candidates)} evaluated")
        print(f"Draft Violations     : {len(report.insufficient_draft_faces)} faces")
        print(f"Potential Undercuts  : {len(report.undercut_faces)} faces ({report.undercut_area_mm2:.1f} mm²)")
        print(f"Slider Candidates    : {len(sliders)}")
        print(f"Transverse Holes     : {len(report.transverse_holes)}")
        print(f"Wall Thickness Regs  : {len(report.wall_thickness_regions)}")
        print(f"Findings Generated   : {len(report.findings)}")
        print(f"Epistemic Summary    : {report.epistemic_summary}")
        print(f"Moldability Index    : {report.moldability_score:.1f} / 100")
        print(f"Artifact Saved       : {json_path}")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[ERROR] Manufacturing review failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if loaded:
            loaded.close()


def main() -> None:
    # Use a two-pass approach to support both subcommands and legacy bare path
    if len(sys.argv) >= 2 and (sys.argv[1] == "mfg-review" or sys.argv[1] == "mfg_review"):
        parser = argparse.ArgumentParser(description="Phase M1 Manufacturing Intelligence & Moldability Review")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        parser.add_argument("--preset", type=str, default="GENERAL_PLASTIC_INJECTION")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_mfg_review_pipeline(step_path, output_dir, args.preset))

    elif len(sys.argv) >= 2 and (sys.argv[1] == "mold-analysis" or sys.argv[1] == "mold_analysis"):
        parser = argparse.ArgumentParser(description="Injection Molding & Slider DFM Engine")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        parser.add_argument("--min-draft", type=float, default=1.5)
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_mold_analysis_pipeline(step_path, output_dir, args.min_draft))

    elif len(sys.argv) >= 2 and (sys.argv[1] == "engineering-review" or sys.argv[1] == "engineering_review"):
        parser = argparse.ArgumentParser(description="Engineering Issue & Recommendation Review")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_engineering_review_pipeline(step_path, output_dir))

    elif len(sys.argv) >= 2 and sys.argv[1] == "ai-review":
        parser = argparse.ArgumentParser(description="Multimodal Engineering AI Review")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        parser.add_argument("--provider", type=str, default="mock", choices=["mock", "claude", "gemini"])
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_ai_review_pipeline(step_path, output_dir, args.provider))

    elif len(sys.argv) >= 2 and sys.argv[1] == "draw":
        # draw subcommand
        parser = argparse.ArgumentParser(description="TechDraw Automated Drawing Generator")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        parser.add_argument("--projection", type=str, default="third", choices=["third", "first"])
        parser.add_argument("--scale", type=float, default=0.0)
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_draw_pipeline(step_path, output_dir, args.projection, args.scale))

    elif len(sys.argv) >= 2 and sys.argv[1] == "dimensions":
        parser = argparse.ArgumentParser(description="Dimension Candidate Engine")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_dimensions_pipeline(step_path, output_dir))

    elif len(sys.argv) >= 2 and (sys.argv[1] == "dimension-drawing" or sys.argv[1] == "dimension_drawing"):
        parser = argparse.ArgumentParser(description="TechDraw Dimension Placement Engine")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_dimensioned_drawing_pipeline(step_path, output_dir))

    elif len(sys.argv) >= 2 and (sys.argv[1] == "complete-dimensions" or sys.argv[1] == "complete_dimensions"):
        parser = argparse.ArgumentParser(description="Complete Engineering Dimensioning Engine")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_complete_dimensioned_drawing_pipeline(step_path, output_dir))

    elif len(sys.argv) >= 2 and sys.argv[1] == "analyse":
        parser = argparse.ArgumentParser(description="CAD Geometry Analyzer")
        parser.add_argument("command")
        parser.add_argument("step_file", type=str)
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_pipeline(step_path, output_dir))

    elif len(sys.argv) >= 2 and sys.argv[1] == "reconstruct":
        parser = argparse.ArgumentParser(description="2D Drawing → 3D CAD Reconstruction")
        parser.add_argument("command")
        parser.add_argument("drawing_file", type=str, help="Path to 2D drawing (SVG, PNG, JPEG, PDF)")
        parser.add_argument("--output-dir", type=str, default="output")
        parser.add_argument("--workspace-dir", type=str, default="workspaces")
        parser.add_argument("--partial-mode", action="store_true", default=True)
        parser.add_argument("--no-partial-mode", action="store_true")
        args = parser.parse_args()
        drawing_path = Path(args.drawing_file)
        partial_mode = args.partial_mode and not args.no_partial_mode
        sys.exit(run_reconstruction_pipeline(drawing_path, workspace_root=Path(args.workspace_dir), partial_mode=partial_mode))

    else:
        # Legacy: bare path argument
        parser = argparse.ArgumentParser(description="Deterministic STEP CAD Geometry Analyzer")
        parser.add_argument("step_file", type=str, help="Path to input STEP file")
        parser.add_argument("--output-dir", type=str, default="output")
        args = parser.parse_args()
        step_path = Path(args.step_file)
        output_dir = Path(args.output_dir)
        sys.exit(run_pipeline(step_path, output_dir))


if __name__ == "__main__":
    main()
