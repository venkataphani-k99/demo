"""CAD Service Layer: Bridges FastAPI endpoints with deterministic CAD engine modules."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.api.schemas import (
    AnalysisSummarySchema,
    BoundingBoxSchema,
    DimensionItemSchema,
    DimensionListResponse,
    FeatureCoverageSchema,
    FeatureItemSchema,
    FeatureListResponse,
    TopologyCountsSchema,
)
from src.api.services.project_service import ProjectService


FREECAD_PYTHON = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class CadService:
    """Invokes CAD inspection, measurement, and feature recognition pipelines."""

    def __init__(self, project_service: Optional[ProjectService] = None):
        self.project_service = project_service or ProjectService()

    def analyze_project(self, project_id: str) -> AnalysisSummarySchema:
        """Run full CAD analysis on the project's STEP file."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent

        self.project_service.update_project_status(project_id, "analyzing")

        try:
            base_name = step_file.stem
            json_analysis = pdir / f"{base_name}_analysis.json"
            txt_report = pdir / f"{base_name}_report.txt"
            json_features = pdir / f"{base_name}_features.json"
            txt_features = pdir / f"{base_name}_features.txt"

            # Run deterministic CAD analysis pipeline via verified FreeCAD environment if not yet analyzed
            if not json_analysis.exists():
                cmd = [
                    FREECAD_PYTHON,
                    "-m", "src.main",
                    str(step_file),
                    "--output-dir", str(pdir),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
                if res.returncode != 0:
                    raise RuntimeError(f"CAD Analysis failed: {res.stderr or res.stdout}")

            if json_analysis.exists():
                self.project_service.register_artifact(project_id, "analysis_json", "json", json_analysis)
            if txt_report.exists():
                self.project_service.register_artifact(project_id, "analysis_report", "txt", txt_report)
            if json_features.exists():
                self.project_service.register_artifact(project_id, "features_json", "json", json_features)
            if txt_features.exists():
                self.project_service.register_artifact(project_id, "features_report", "txt", txt_features)

            # Load analysis data
            data = json.loads(json_analysis.read_text(encoding="utf-8"))
            topo = data.get("topology", {})
            bbox = data.get("bounding_box", {})

            summary = AnalysisSummarySchema(
                project_id=project_id,
                filename=meta["filename"],
                units=data.get("units", "mm"),
                topology=TopologyCountsSchema(
                    solids=topo.get("solids", 0),
                    shells=topo.get("shells", 0),
                    faces=topo.get("faces", 0),
                    edges=topo.get("edges", 0),
                    vertices=topo.get("vertices", 0),
                ),
                bounding_box=BoundingBoxSchema(
                    x_min=bbox.get("min_x", 0.0),
                    x_max=bbox.get("max_x", 0.0),
                    y_min=bbox.get("min_y", 0.0),
                    y_max=bbox.get("max_y", 0.0),
                    z_min=bbox.get("min_z", 0.0),
                    z_max=bbox.get("max_z", 0.0),
                    x_length=bbox.get("length_x", 0.0),
                    y_length=bbox.get("length_y", 0.0),
                    z_length=bbox.get("length_z", 0.0),
                ),
                surface_types=data.get("surface_classification", {}),
                feature_count=len(data.get("features", [])),
                volume_mm3=data.get("total_volume", 0.0),
                surface_area_mm2=data.get("total_surface_area", 0.0),
                sha256_hash=meta.get("sha256_hash"),
                file_size_bytes=meta.get("file_size_bytes"),
                source_file=str(step_file),
                analysis_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

            self.project_service.update_project_status(project_id, "analyzed")
            return summary

        except Exception as e:
            self.project_service.update_project_status(project_id, "failed", str(e))
            raise

    def get_features(self, project_id: str) -> FeatureListResponse:
        """Retrieve recognized features for a project."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent
        base_name = step_file.stem
        feat_json = pdir / f"{base_name}_features.json"

        if not feat_json.exists():
            # Trigger analysis if not yet analyzed
            self.analyze_project(project_id)

        feat_data = json.loads(feat_json.read_text(encoding="utf-8"))
        raw_feats = feat_data.get("features", [])

        features = [
            FeatureItemSchema(
                id=f["feature_id"],
                type=f["feature_type"],
                status=f.get("status", "confirmed"),
                dimensions=f.get("dimensions", {}),
                source_entities=f.get("source_entities", []),
                axis=f.get("axis"),
                position=f.get("position"),
            )
            for f in raw_feats
        ]

        return FeatureListResponse(
            project_id=project_id,
            total_features=len(features),
            features=features,
        )

    def get_dimensions(self, project_id: str) -> DimensionListResponse:
        """Retrieve candidate dimensions, dependencies, redundancy, and view assignments."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent
        base_name = step_file.stem

        dim_json = pdir / f"{base_name}_complete_dimensions.json"
        if not dim_json.exists():
            # Run complete dimensioning pipeline to produce dataset
            cmd = [
                FREECAD_PYTHON,
                "-m", "src.main",
                "complete-dimensions",
                str(step_file),
                "--output-dir", str(pdir),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            if res.returncode != 0:
                raise RuntimeError(f"Dimension extraction failed: {res.stderr or res.stdout}")

        data = json.loads(dim_json.read_text(encoding="utf-8"))
        items = [
            DimensionItemSchema(
                id=i["dimension_id"] if "dimension_id" in i else i["id"],
                type=i["dimension_type"] if "dimension_type" in i else i["type"],
                value=i["value"],
                display_value=i.get("display_value", f"{i['value']} mm"),
                unit=i.get("unit", "mm"),
                semantic_role=i.get("semantic_role", "functional"),
                priority=i.get("priority", "medium"),
                dependency_type=i.get("dependency_type", "independent"),
                depends_on=i.get("depends_on", []),
                source_feature=i.get("source_feature"),
                source_entities=i.get("source_entities", []),
                status=i.get("validation_status", i.get("status", "valid")),
                selected_view=i.get("selected_view"),
                projection_status=i.get("projection_status", "unsuitable"),
                placement_status=i.get("placement_status", i.get("status", "excluded")),
                x_mm=i.get("x_mm", 0.0),
                y_mm=i.get("y_mm", 0.0),
                reason=i.get("reason", ""),
                category=i.get("category", "placed" if i.get("placement_status") == "placed" else "excluded"),
                exclusion_reason=i.get("exclusion_reason", i.get("reason") if i.get("placement_status") != "placed" else None),
            )
            for i in data.get("items", data.get("candidates", []))
        ]

        coverages = [
            FeatureCoverageSchema(
                feature_id=c["feature_id"],
                feature_type=c["feature_type"],
                coverage_status=c["coverage_status"],
                dimension_ids=c["dimension_ids"],
                placed_dimension_ids=c["placed_dimension_ids"],
                missing_aspects=c.get("missing_aspects", []),
            )
            for c in data.get("feature_coverages", [])
        ]

        raw_count = data.get("raw_measurements_count", len(items) * 3)
        cand_count = data.get("engineering_candidates_count", len(items))

        return DimensionListResponse(
            project_id=project_id,
            raw_measurements_count=raw_count,
            engineering_candidates_count=cand_count,
            total_candidates=data.get("total_candidates", len(items)),
            placed_count=data.get("placed_count", sum(1 for i in items if i.placement_status == "placed")),
            excluded_count=data.get("excluded_count", sum(1 for i in items if i.placement_status != "placed")),
            dimensions=items,
            feature_coverages=coverages,
        )

    def get_mesh(self, project_id: str) -> Dict[str, Any]:
        """Generate or retrieve 3D B-Rep mesh geometry for Three.js rendering."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent
        base_name = step_file.stem
        mesh_file = pdir / f"{base_name}_mesh.json"

        if not mesh_file.exists():
            cmd = [
                FREECAD_PYTHON,
                "-m", "src.cad.mesh_exporter",
                str(step_file),
                str(mesh_file),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            if res.returncode != 0:
                raise RuntimeError(f"3D mesh generation failed for {base_name}: {res.stderr or res.stdout}")

        return json.loads(mesh_file.read_text(encoding="utf-8"))

    def get_engineering_intelligence(self, project_id: str) -> Dict[str, Any]:
        """Generate or retrieve Phase 20 Engineering Design Intelligence & Verification Report."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        pdir = step_file.parent
        base_name = step_file.stem
        intel_file = pdir / f"{base_name}_engineering_intelligence.json"

        if intel_file.exists():
            try:
                return json.loads(intel_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Generate deterministically via isolated FreeCAD environment
        cmd = [
            FREECAD_PYTHON,
            "-c",
            f"from src.cad.step_loader import load_step; from src.cad.engineering_intelligence_engine import EngineeringIntelligenceEngine; from pathlib import Path; import json; res = load_step(Path(r'{step_file}')); engine = EngineeringIntelligenceEngine(); report = engine.analyze_model(res, '{step_file.name}'); res.close(); Path(r'{intel_file}').write_text(json.dumps(report.to_dict(), indent=2), encoding='utf-8')",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if intel_file.exists():
            return json.loads(intel_file.read_text(encoding="utf-8"))

        raise RuntimeError(f"Engineering intelligence extraction failed for {step_file.name}: {res.stderr or res.stdout}")

    def get_ai_engineering_review(self, project_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Generate or retrieve Phase 24 AI Engineering Design Review grounded in OCCT evidence."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        pdir = step_file.parent
        base_name = step_file.stem
        review_file = pdir / f"{base_name}_ai_engineering_review.json"

        if review_file.exists() and not force_refresh:
            try:
                return json.loads(review_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 1. Fetch deterministic OCCT evidence dataset
        intel_data = self.get_engineering_intelligence(project_id)

        # 2. Build structured evidence package
        from src.intelligence.ai_reasoning import build_evidence_package, get_ai_reasoning_provider
        evidence_pkg = build_evidence_package(intel_data)

        # 3. Analyze via provider with evidence validator
        provider = get_ai_reasoning_provider()
        res = provider.analyze_engineering_evidence(evidence_pkg)
        res_dict = res.to_dict()

        review_file.write_text(json.dumps(res_dict, indent=2), encoding="utf-8")
        return res_dict

    def ask_ai_engineering_question(self, project_id: str, question: str) -> Dict[str, Any]:
        """Answer engineering design review questions grounded in OCCT evidence."""
        intel_data = self.get_engineering_intelligence(project_id)
        from src.intelligence.ai_reasoning import build_evidence_package, get_ai_reasoning_provider
        evidence_pkg = build_evidence_package(intel_data)
        provider = get_ai_reasoning_provider()
        qa_res = provider.answer_engineering_question(question, evidence_pkg)
        return qa_res.to_dict()

    def get_cad_drawing_consistency(self, project_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Generate or retrieve Phase 25 CAD ↔ Drawing Consistency Audit."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        pdir = step_file.parent
        base_name = step_file.stem
        consistency_file = pdir / f"{base_name}_cad_drawing_consistency.json"

        if consistency_file.exists() and not force_refresh:
            try:
                return json.loads(consistency_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 1. Locate corresponding drawing file in project
        drawing_file = None
        candidate_names = [
            f"{base_name}_industrial_drawing.svg",
            f"{base_name}_drawing.svg",
            f"{base_name}_complete_dimensioned.svg",
            f"{base_name}.pdf",
            f"{base_name}.svg",
        ]
        for cname in candidate_names:
            cpath = pdir / cname
            if cpath.exists():
                drawing_file = cpath
                break

        # If not found by name, pick any svg in pdir
        if not drawing_file:
            svgs = list(pdir.glob("*.svg"))
            if svgs:
                drawing_file = svgs[0]

        from src.intelligence.drawing_consistency import (
            AIConsistencyReviewer,
            ConsistencyEngine,
            DrawingEvidenceExtractor,
        )

        # 2. Extract Drawing Evidence
        if drawing_file and drawing_file.exists():
            drawing_pkg = DrawingEvidenceExtractor.extract_from_svg(drawing_file)
        else:
            # Fallback drawing baseline
            drawing_pkg = DrawingEvidenceExtractor._extract_from_raw_text("", f"{base_name}_drawing.svg")

        # 3. Retrieve CAD B-Rep Engineering Facts
        intel_data = self.get_engineering_intelligence(project_id)
        cad_features = intel_data.get("feature_graph", [])
        cad_dimensions = intel_data.get("classified_dimensions", [])

        # 4. Deterministic Consistency Evaluation
        matches, summary = ConsistencyEngine.audit_consistency(
            cad_features=cad_features,
            cad_dimensions=cad_dimensions,
            drawing_package=drawing_pkg,
        )

        # 5. AI Reasoning & Explanation Layer
        ai_review = AIConsistencyReviewer.generate_consistency_review(
            project_id=project_id,
            matches=matches,
            summary=summary,
            drawing_package=drawing_pkg,
        )

        res_dict = {
            "project_id": project_id,
            "drawing_filename": drawing_pkg.drawing_filename,
            "drawing_package": drawing_pkg.to_dict(),
            "matches": [m.to_dict() for m in matches],
            "summary": summary.to_dict(),
            "ai_review": ai_review,
        }

        consistency_file.write_text(json.dumps(res_dict, indent=2), encoding="utf-8")
        return res_dict

    def ask_cad_drawing_question(self, project_id: str, question: str) -> Dict[str, Any]:
        """Answer engineering consistency questions grounded in CAD facts and drawing evidence."""
        consistency_data = self.get_cad_drawing_consistency(project_id)
        from src.intelligence.drawing_consistency import (
            AIConsistencyReviewer,
            CADDrawingMatchItem,
            ConsistencyAuditSummary,
            ConsistencyStatus,
        )

        matches = []
        for m in consistency_data.get("matches", []):
            matches.append(
                CADDrawingMatchItem(
                    match_id=m["match_id"],
                    cad_feature_id=m.get("cad_feature_id"),
                    cad_entity_id=m.get("cad_entity_id"),
                    cad_entity_type=m.get("cad_entity_type", "FACE"),
                    cad_nominal_value=m.get("cad_nominal_value", 0.0),
                    cad_property=m.get("cad_property", "diameter_mm"),
                    cad_measurement_method=m.get("cad_measurement_method", "OCCT_GeomCylinder_Radius"),
                    drawing_evidence_id=m.get("drawing_evidence_id"),
                    drawing_nominal_value=m.get("drawing_nominal_value"),
                    drawing_tolerance_raw=m.get("drawing_tolerance_raw"),
                    drawing_text_raw=m.get("drawing_text_raw"),
                    drawing_view=m.get("drawing_view"),
                    drawing_bbox=m.get("drawing_bbox", [0, 0, 0, 0]),
                    consistency_status=ConsistencyStatus(m.get("consistency_status", "CONSISTENT")),
                    numerical_delta_mm=m.get("numerical_delta_mm", 0.0),
                    match_confidence=m.get("match_confidence", 1.0),
                    match_reason=m.get("match_reason", ""),
                    epistemic_provenance=m.get("epistemic_provenance", ""),
                    engineering_rationale=m.get("engineering_rationale", ""),
                    recommended_action=m.get("recommended_action"),
                )
            )

        summary_raw = consistency_data.get("summary", {})
        summary = ConsistencyAuditSummary(
            total_cad_features_audited=summary_raw.get("total_cad_features_audited", 0),
            total_drawing_dimensions_found=summary_raw.get("total_drawing_dimensions_found", 0),
            matched_count=summary_raw.get("matched_count", 0),
            consistent_count=summary_raw.get("consistent_count", 0),
            conflict_count=summary_raw.get("conflict_count", 0),
            cannot_verify_count=summary_raw.get("cannot_verify_count", 0),
            missing_count=summary_raw.get("missing_count", 0),
            ambiguous_count=summary_raw.get("ambiguous_count", 0),
            dimension_coverage_percent=summary_raw.get("dimension_coverage_percent", 0.0),
        )

        return AIConsistencyReviewer.answer_consistency_question(question, matches, summary)

    def get_mold_analysis(self, project_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Generate or retrieve Phase 26 Injection Molding & Slider DFM Report."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        pdir = step_file.parent
        base_name = step_file.stem
        mold_file = pdir / f"{base_name}_mold_analysis.json"

        if mold_file.exists() and not force_refresh:
            try:
                return json.loads(mold_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Execute via verified FreeCAD subprocess
        cmd = [
            FREECAD_PYTHON,
            "-m", "src.main",
            "mold-analysis",
            str(step_file),
            "--output-dir", str(pdir),
            "--min-draft", "1.5",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            raise RuntimeError(f"Mold analysis failed: {res.stderr or res.stdout}")

        if mold_file.exists():
            self.project_service.register_artifact(project_id, "mold_analysis_json", "json", mold_file)
            return json.loads(mold_file.read_text(encoding="utf-8"))
        else:
            raise RuntimeError("Mold analysis output JSON not generated.")

    def evaluate_custom_mold_direction(
        self,
        project_id: str,
        direction: List[float],
        min_draft_deg: float = 1.5,
        cavity_pressure_bar: float = 400.0,
    ) -> Dict[str, Any]:
        """Dynamically re-evaluates draft angles, undercuts and sliders along a user-specified 3D draw vector."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        step_path_str = step_file.as_posix()
        py_script = f"""
import json, sys
from pathlib import Path
from src.cad.step_loader import load_step
from src.cad.mold_analyzer import MoldabilityAnalyzer
from src.cad.slider_locator import SliderLocator

loaded = load_step(Path(r'{step_path_str}'))
try:
    shape = loaded.primary_shape or loaded.shape
    analyzer = MoldabilityAnalyzer(
        shape=shape,
        min_draft_deg={min_draft_deg},
        cavity_pressure_bar={cavity_pressure_bar},
    )
    report = analyzer.analyze(
        custom_pull_direction={direction},
        project_id="{project_id}",
    )
    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()
    report_dict = report.to_dict()
    report_dict["sliders"] = [s.to_dict() for s in sliders]
    print("__JSON_START__" + json.dumps(report_dict) + "__JSON_END__")
finally:
    loaded.close()
"""
        cmd = [FREECAD_PYTHON, "-c", py_script]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            raise RuntimeError(f"Direction evaluation failed: {res.stderr or res.stdout}")

        stdout = res.stdout
        if "__JSON_START__" in stdout and "__JSON_END__" in stdout:
            json_str = stdout.split("__JSON_START__")[1].split("__JSON_END__")[0]
            return json.loads(json_str)
        else:
            raise RuntimeError(f"Invalid script output: {stdout}")

    def get_manufacturing_review(
        self,
        project_id: str,
        preset_id: str = "GENERAL_PLASTIC_INJECTION",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Generate or retrieve complete Phase M1 Manufacturing Review with AI agenda."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        pdir = step_file.parent
        base_name = step_file.stem
        review_file = pdir / f"{base_name}_{preset_id}_mfg_review.json"

        if review_file.exists() and not force_refresh:
            try:
                return json.loads(review_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        step_path_str = step_file.as_posix()
        py_script = f"""
import json, sys
from pathlib import Path
from src.cad.step_loader import load_step
from src.cad.mold_analyzer import MoldabilityAnalyzer
from src.cad.slider_locator import SliderLocator
from src.cad.ai_manufacturing_reviewer import AIManufacturingReviewer

loaded = load_step(Path(r'{step_path_str}'))
try:
    shape = loaded.primary_shape or loaded.shape
    analyzer = MoldabilityAnalyzer(
        shape=shape,
        process_preset_id="{preset_id}",
    )
    report = analyzer.analyze(project_id="{project_id}")
    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()
    ai_report = AIManufacturingReviewer.generate_review(report)

    report_dict = report.to_dict()
    report_dict["sliders"] = [s.to_dict() for s in sliders]
    report_dict["ai_review"] = ai_report.to_dict()

    print("__JSON_START__" + json.dumps(report_dict) + "__JSON_END__")
finally:
    loaded.close()
"""
        cmd = [FREECAD_PYTHON, "-c", py_script]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            raise RuntimeError(f"Manufacturing review failed: {res.stderr or res.stdout}")

        stdout = res.stdout
        if "__JSON_START__" in stdout and "__JSON_END__" in stdout:
            json_str = stdout.split("__JSON_START__")[1].split("__JSON_END__")[0]
            data = json.loads(json_str)
            review_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.project_service.register_artifact(project_id, "mfg_review_json", "json", review_file)
            return data
        else:
            raise RuntimeError(f"Invalid script output: {stdout}")

    def evaluate_custom_mfg_review(
        self,
        project_id: str,
        direction: List[float],
        min_draft_deg: Optional[float] = None,
        cavity_pressure_bar: Optional[float] = None,
        preset_id: str = "GENERAL_PLASTIC_INJECTION",
    ) -> Dict[str, Any]:
        """Dynamically re-evaluates complete Phase M1 Manufacturing Review along a user-specified draw vector."""
        meta = self.project_service.get_project_metadata(project_id)
        step_file = Path(meta["step_file"])
        if not step_file.is_absolute():
            step_file = (PROJECT_ROOT / step_file).resolve()

        step_path_str = step_file.as_posix()
        draft_arg = f"min_draft_deg={min_draft_deg}," if min_draft_deg is not None else ""
        press_arg = f"cavity_pressure_bar={cavity_pressure_bar}," if cavity_pressure_bar is not None else ""

        py_script = f"""
import json, sys
from pathlib import Path
from src.cad.step_loader import load_step
from src.cad.mold_analyzer import MoldabilityAnalyzer
from src.cad.slider_locator import SliderLocator
from src.cad.ai_manufacturing_reviewer import AIManufacturingReviewer

loaded = load_step(Path(r'{step_path_str}'))
try:
    shape = loaded.primary_shape or loaded.shape
    analyzer = MoldabilityAnalyzer(
        shape=shape,
        process_preset_id="{preset_id}",
        {draft_arg}
        {press_arg}
    )
    report = analyzer.analyze(
        custom_pull_direction={direction},
        project_id="{project_id}",
    )
    locator = SliderLocator(shape=shape, mold_report=report)
    sliders = locator.locate_sliders()
    ai_report = AIManufacturingReviewer.generate_review(report)

    report_dict = report.to_dict()
    report_dict["sliders"] = [s.to_dict() for s in sliders]
    report_dict["ai_review"] = ai_report.to_dict()

    print("__JSON_START__" + json.dumps(report_dict) + "__JSON_END__")
finally:
    loaded.close()
"""
        cmd = [FREECAD_PYTHON, "-c", py_script]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            raise RuntimeError(f"Custom review evaluation failed: {res.stderr or res.stdout}")

        stdout = res.stdout
        if "__JSON_START__" in stdout and "__JSON_END__" in stdout:
            json_str = stdout.split("__JSON_START__")[1].split("__JSON_END__")[0]
            return json.loads(json_str)
        else:
            raise RuntimeError(f"Invalid script output: {stdout}")





