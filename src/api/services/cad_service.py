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
from src.cad.freecad_env import get_freecad_python


FREECAD_PYTHON = get_freecad_python()
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

