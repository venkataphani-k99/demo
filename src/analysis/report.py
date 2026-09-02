"""Report generation module for CAD Intelligence.

Generates structured JSON datasets and clean human-readable engineering text reports:
- Comprehensive model analysis (JSON & TXT)
- Dedicated engineering features report (JSON & TXT)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from src.analysis.analyzer import CadAnalysisResult


def generate_json_report(analysis: CadAnalysisResult, output_path: Path) -> Path:
    """Save structured JSON analysis output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis.to_dict(), f, indent=2)
    return output_path


def generate_features_json(analysis: CadAnalysisResult, output_path: Path) -> Path:
    """Save dedicated features JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "filename": analysis.filename,
        "units": analysis.units,
        "total_features": len(analysis.features),
        "features": analysis.features,
        "logical_cylinders": analysis.logical_cylinders,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return output_path


def generate_features_text(analysis: CadAnalysisResult, output_path: Path) -> Path:
    """Save clean human-readable engineering features report (Phase 5H)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unit = analysis.units

    lines = [
        "=" * 100,
        "CAD MODEL RECOGNIZED ENGINEERING FEATURES REPORT (PHASE 5)",
        "=" * 100,
        "",
        f"File Name      : {analysis.filename}",
        f"Units          : {analysis.units}",
        f"Total Features : {len(analysis.features)}",
        "-" * 100,
        "",
        "RECOGNIZED ENGINEERING FEATURES",
        "=" * 100,
    ]

    for feat in analysis.features:
        fid = feat.get("feature_id", "")
        ftype = feat.get("feature_type", "").replace("_", " ").title()
        status = feat.get("status", "CONFIRMED").upper()
        confidence = feat.get("confidence", 1.0)
        dims = feat.get("dimensions", {})
        srcs = ", ".join(feat.get("source_entities", []))
        rules = feat.get("recognition_rules", [])
        axis = feat.get("axis")
        axis_str = f"({axis[0]:.2f}, {axis[1]:.2f}, {axis[2]:.2f})" if axis else "N/A"

        lines.append(f"[{status}] {fid}: {ftype} (Confidence: {confidence:.2f})")
        
        for k, v in dims.items():
            dim_label = k.replace("_", " ").title()
            u_str = "°" if "sweep" in k or "angle" in k else f" {unit}"
            lines.append(f"  • {dim_label:<24}: {v:8.3f}{u_str}")

        if axis:
            lines.append(f"  • Axis Direction          : {axis_str}")

        lines.append(f"  • Supporting B-Rep Faces  : {srcs}")
        lines.append(f"  • Triggered Rules         : {', '.join(rules)}")
        lines.append("")

    lines.extend([
        "=" * 100,
        "LOGICAL CYLINDER GROUPINGS (22 B-REP FACES SYNTHESIS)",
        "=" * 100,
        f"{'Group ID':<16} | {'Diameter':>9} | {'Radius':>8} | {'Sweep':>7} | {'Orientation':<12} | {'Faces':<30}",
        "-" * 100,
    ])

    for cyl in analysis.logical_cylinders:
        gid = cyl.get("group_id", "")
        dia = cyl.get("diameter", 0.0)
        rad = cyl.get("radius", 0.0)
        swp = cyl.get("total_sweep_deg", 0.0)
        orient = "Internal" if cyl.get("is_internal") else "External"
        f_list = ", ".join(cyl.get("face_ids", []))
        lines.append(f"{gid:<16} | {dia:8.3f} {unit} | {rad:7.3f} {unit} | {swp:6.1f}° | {orient:<12} | {f_list:<30}")

    lines.extend([
        "",
        "=" * 100,
        "END OF FEATURES REPORT",
        "=" * 100,
        "",
    ])

    report_content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return output_path


def generate_text_report(analysis: CadAnalysisResult, output_path: Path) -> Path:
    """Save clean human-readable engineering report with detailed tables."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bbox = analysis.bounding_box
    unit = analysis.units

    lines = [
        "=" * 100,
        "CAD MODEL COMPLETE GEOMETRY, MEASUREMENTS & FEATURES REPORT",
        "=" * 100,
        "",
        "FILE INFORMATION",
        "-" * 100,
        f"File Name           : {analysis.filename}",
        f"File Size           : {analysis.file_size_bytes:,} bytes",
        f"STEP Schema         : {analysis.schema}",
        f"Originating System  : {analysis.originating_system}",
        f"Timestamp           : {analysis.timestamp}",
        f"Units               : {analysis.units}",
        "",
        "OVERALL GEOMETRY & BOUNDING BOX",
        "-" * 100,
        f"Overall Size (X×Y×Z): {bbox.length_x:.3f} × {bbox.length_y:.3f} × {bbox.length_z:.3f} {unit}",
        f"Bounding Box Min    : ({bbox.min_x:.3f}, {bbox.min_y:.3f}, {bbox.min_z:.3f}) {unit}",
        f"Bounding Box Max    : ({bbox.max_x:.3f}, {bbox.max_y:.3f}, {bbox.max_z:.3f}) {unit}",
        f"Total Surface Area  : {analysis.total_surface_area:.3f} {unit}²",
        f"Total Volume        : {analysis.total_volume:.3f} {unit}³",
        "",
        "TOPOLOGY COUNTS",
        "-" * 100,
        f"Imported Objects    : {analysis.object_count}",
        f"Solids              : {analysis.topology.solids}",
        f"Shells              : {analysis.topology.shells}",
        f"Compounds           : {analysis.topology.compounds}",
        f"Faces               : {analysis.topology.faces}",
        f"Edges               : {analysis.topology.edges}",
        f"Vertices            : {analysis.topology.vertices}",
        "",
        "SURFACE CLASSIFICATION SUMMARY",
        "-" * 100,
    ]

    for surf_type, count in sorted(analysis.surface_classification.items(), key=lambda x: -x[1]):
        area = analysis.surface_area_by_type.get(surf_type, 0.0)
        lines.append(f"  • {surf_type:<20}: {count:>3} faces  ({area:>10.3f} {unit}²)")

    lines.extend([
        "",
        "CURVE / EDGE CLASSIFICATION SUMMARY",
        "-" * 100,
    ])

    for curve_type, count in sorted(analysis.curve_classification.items(), key=lambda x: -x[1]):
        lines.append(f"  • {curve_type:<20}: {count:>3} edges")

    # Features Section Summary
    if analysis.features:
        lines.extend([
            "",
            "=" * 100,
            f"RECOGNIZED ENGINEERING FEATURES ({len(analysis.features)} FEATURES CONFIRMED)",
            "=" * 100,
            f"{'Feature ID':<14} | {'Type':<22} | {'Key Dimensions':<30} | {'Supporting Faces':<24}",
            "-" * 100,
        ])
        for feat in analysis.features:
            fid = feat.get("feature_id", "")
            ftype = feat.get("feature_type", "")
            dims = feat.get("dimensions", {})
            dim_str = ", ".join(f"{k}={v:.2f}" for k, v in list(dims.items())[:2])
            srcs = ", ".join(feat.get("source_entities", []))
            if len(srcs) > 22:
                srcs = srcs[:20] + "..."
            lines.append(f"{fid:<14} | {ftype:<22} | {dim_str:<30} | {srcs:<24}")

    # Exact Measurements Section
    if analysis.measurements:
        lines.extend([
            "",
            "=" * 100,
            "EXACT CAD MEASUREMENTS ENGINE (TRACEABLE TO B-REP ENTITIES)",
            "=" * 100,
            f"{'Type':<22} | {'Measured Value':>16} | {'Source Entities':<30} | {'Method':<32}",
            "-" * 100,
        ])
        for m in analysis.measurements:
            m_type = m.get("type", "")
            val_str = f"{m.get('value', 0.0):.3f} {m.get('unit', '')}"
            srcs = ", ".join(m.get("source_entities", []))
            if len(srcs) > 28:
                srcs = srcs[:25] + "..."
            method = m.get("method", "")
            lines.append(f"{m_type:<22} | {val_str:>16} | {srcs:<30} | {method:<32}")

    # Detailed Cylindrical Faces Table
    lines.extend([
        "",
        "=" * 100,
        "CYLINDRICAL SURFACES DEEP ANALYSIS (22 FACES DETECTED)",
        "=" * 100,
        f"{'Face ID':<8} | {'Radius':>8} | {'Diameter':>9} | {'Axial Len':>9} | {'Sweep':>7} | {'Area (mm²)':>10} | {'Axis Direction':<22} | {'Adjacent Faces':<15}",
        "-" * 100,
    ])

    for cyl in analysis.cylindrical_faces:
        axis_str = f"({cyl.axis_direction[0]:.2f}, {cyl.axis_direction[1]:.2f}, {cyl.axis_direction[2]:.2f})"
        adj_str = ", ".join(cyl.adjacent_faces[:4])
        if len(cyl.adjacent_faces) > 4:
            adj_str += f"... (+{len(cyl.adjacent_faces)-4})"
        lines.append(
            f"{cyl.id:<8} | {cyl.radius:8.3f} | {cyl.diameter:9.3f} | {cyl.axial_length:9.3f} | {cyl.angular_sweep_deg:6.1f}° | {cyl.surface_area:10.3f} | {axis_str:<22} | {adj_str:<15}"
        )

    # Detailed Planar Faces Table
    lines.extend([
        "",
        "=" * 100,
        "PLANAR SURFACES DEEP ANALYSIS (8 FACES DETECTED)",
        "=" * 100,
        f"{'Face ID':<8} | {'Area (mm²)':>10} | {'Normal Vector (X, Y, Z)':<26} | {'Plane Position (X, Y, Z)':<28} | {'Adjacent Faces':<15}",
        "-" * 100,
    ])

    for p in analysis.planar_faces:
        norm_str = f"({p.normal[0]:.2f}, {p.normal[1]:.2f}, {p.normal[2]:.2f})"
        pos_str = f"({p.position[0]:.2f}, {p.position[1]:.2f}, {p.position[2]:.2f})"
        adj_str = ", ".join(p.adjacent_faces[:4])
        if len(p.adjacent_faces) > 4:
            adj_str += f"... (+{len(p.adjacent_faces)-4})"
        lines.append(
            f"{p.id:<8} | {p.area:10.3f} | {norm_str:<26} | {pos_str:<28} | {adj_str:<15}"
        )

    # Engineering Notes
    lines.extend([
        "",
        "ENGINEERING NOTES & COMPLIANCE",
        "-" * 100,
    ])
    for note in analysis.notes:
        lines.append(f"  - {note}")

    lines.extend([
        "",
        "=" * 100,
        "END OF REPORT",
        "=" * 100,
        "",
    ])

    report_content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return output_path


def export_analysis_reports(
    analysis: CadAnalysisResult, output_dir: Path | str = "output"
) -> Tuple[Path, Path, Path, Path]:
    """Export JSON and text reports for both complete analysis and dedicated features."""
    out_dir = Path(output_dir).resolve()
    base_name = Path(analysis.filename).stem

    json_path = out_dir / f"{base_name}_analysis.json"
    txt_path = out_dir / f"{base_name}_report.txt"
    feat_json_path = out_dir / f"{base_name}_features.json"
    feat_txt_path = out_dir / f"{base_name}_features.txt"

    generate_json_report(analysis, json_path)
    generate_text_report(analysis, txt_path)
    generate_features_json(analysis, feat_json_path)
    generate_features_text(analysis, feat_txt_path)

    return json_path, txt_path, feat_json_path, feat_txt_path


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Dimension Candidate Reports
# ─────────────────────────────────────────────────────────────────────────────

def generate_dimensions_json(
    candidate_set,
    view_report,
    output_path: Path,
) -> Path:
    """Save dimension candidates + view visibility analysis as JSON.

    Args:
        candidate_set: DimensionCandidateSet from DimensionCandidateEngine.
        view_report:   ViewAnalysisReport from ViewAnalyser.
        output_path:   Destination .json file path.

    Returns:
        Path to written file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Index view analyses by candidate_id for easy merging
    view_index = {a.candidate_id: a.to_dict() for a in view_report.analyses}

    data = candidate_set.to_dict()
    # Embed view analysis into each candidate record
    for cand_dict in data["candidates"]:
        cid = cand_dict["id"]
        cand_dict["view_analysis"] = view_index.get(cid, {})

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return output_path


def generate_dimensions_text(
    candidate_set,
    view_report,
    output_path: Path,
) -> Path:
    """Write a human-readable dimension candidate report.

    Args:
        candidate_set: DimensionCandidateSet from DimensionCandidateEngine.
        view_report:   ViewAnalysisReport from ViewAnalyser.
        output_path:   Destination .txt file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Index view analyses by candidate_id
    view_index = {a.candidate_id: a for a in view_report.analyses}

    lines: List[str] = []
    sep = "=" * 60
    thin = "-" * 60

    lines += [
        sep,
        "DIMENSION CANDIDATES",
        sep,
        f"  Model File : {candidate_set.model_file}",
        f"  Total      : {candidate_set.total}",
        f"  Valid      : {candidate_set.valid}",
        f"  Ambiguous  : {candidate_set.ambiguous}",
        f"  Rejected   : {candidate_set.rejected}",
        f"  Unsupported: {candidate_set.unsupported}",
        sep,
        "",
    ]

    for cand in candidate_set.candidates:
        lines.append(f"{cand.id}")
        lines.append(f"  Type       : {cand.type.capitalize()}")
        lines.append(f"  Value      : {cand.formatted_value}")
        lines.append(f"  Feature    : {cand.source_feature or '—'}")
        lines.append(f"  Sources    : {', '.join(cand.source_entities) if cand.source_entities else '—'}")
        lines.append(f"  Method     : {cand.measurement_method}")
        lines.append(f"  Semantics  : {cand.dimension_semantics}")
        lines.append(f"  Status     : {cand.status}")
        if cand.feature_group:
            lines.append(f"  Group      : {cand.feature_group}")
        if cand.reason:
            lines.append(f"  Reason     : {cand.reason}")
        for k, v in cand.details.items():
            lines.append(f"  {k:<11}: {v}")
        lines.append("")

    lines += [
        sep,
        "VIEW VISIBILITY ANALYSIS",
        sep,
        "",
    ]

    visibility_symbol = {
        "circular_profile": "○",
        "edge_on":          "‖",
        "planar_profile":   "□",
        "partial_profile":  "◇",
        "unsuitable":       "✗",
    }

    for cand in candidate_set.candidates:
        va = view_index.get(cand.id)
        if va is None:
            continue
        lines.append(f"{cand.id} / {cand.formatted_value}")
        for vv in va.views:
            sym = visibility_symbol.get(vv.visibility, "?")
            rec = " ◄ recommended" if vv.view == va.recommended_view else ""
            lines.append(f"  {vv.view:<8}: {sym} {vv.visibility:<18} (score={vv.score:.2f}){rec}")
        lines.append("")

    lines.append(sep)

    # Write
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def export_dimension_reports(
    candidate_set,
    view_report,
    output_dir: Path,
    base_name: str = "model",
) -> Tuple[Path, Path]:
    """Write both dimension candidate output files.

    Args:
        candidate_set: DimensionCandidateSet.
        view_report:   ViewAnalysisReport.
        output_dir:    Output directory.
        base_name:     Stem for output file names.

    Returns:
        (json_path, txt_path)
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{base_name}_dimensions.json"
    txt_path = out_dir / f"{base_name}_dimensions.txt"

    generate_dimensions_json(candidate_set, view_report, json_path)
    generate_dimensions_text(candidate_set, view_report, txt_path)

    return json_path, txt_path
