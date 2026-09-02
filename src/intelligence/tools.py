"""Agent CAD Tool Registry: Structured, programmatic tool interface wrapping FreeCAD / OCCT."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import FreeCAD

from src.cad.step_loader import load_step
from src.cad.topology import build_topology_graph, TopologyGraph
from src.cad.measurements import MeasurementEngine
from src.cad.features import recognize_cad_features, RecognizedFeature
from src.cad.dimensions import DimensionCandidate, DimensionCandidateEngine, DimensionCandidateSet
from src.cad.view_analysis import analyse_view_visibility, ViewAnalysisReport, STANDARD_VIEWS
from src.cad.dimension_dependencies import DimensionDependencyAnalyser, DependencyAnalysisResult
from src.cad.dimension_redundancy import DimensionRedundancyAnalyser, RedundancyAnalysisResult


class CADToolRegistry:
    """Provides structured, deterministic CAD query tools for AI reasoning agents."""

    def __init__(self, step_path: Path):
        self.step_path = Path(step_path).resolve()
        load_res = load_step(self.step_path)
        self.shape = load_res.primary_shape
        self.engine = MeasurementEngine(self.shape)
        self.topo = build_topology_graph(self.shape)
        self.features = recognize_cad_features(self.shape, self.topo, self.engine)
        load_res.close()

        dim_engine = DimensionCandidateEngine(self.features, self.engine, self.topo, self.step_path.name)
        self.candidate_set = dim_engine.generate()
        self.view_report = analyse_view_visibility(self.candidate_set)

        dep_analyser = DimensionDependencyAnalyser()
        self.dep_result = dep_analyser.analyse(self.candidate_set, self.engine, self.topo)

        red_analyser = DimensionRedundancyAnalyser()
        self.red_result = red_analyser.analyse(self.candidate_set, self.dep_result, self.features)

    def get_model_summary(self) -> Dict[str, Any]:
        """Tool: Retrieve units, bounding box extents, volume, surface area, and topology counts."""
        bbox = self.shape.BoundBox
        return {
            "model_file": self.step_path.name,
            "units": "mm",
            "solids": len(self.shape.Solids),
            "faces": len(self.shape.Faces),
            "edges": len(self.shape.Edges),
            "vertices": len(self.shape.Vertexes),
            "bounding_box": {
                "x_len": round(bbox.XLength, 4),
                "y_len": round(bbox.YLength, 4),
                "z_len": round(bbox.ZLength, 4),
                "min": [round(bbox.XMin, 4), round(bbox.YMin, 4), round(bbox.ZMin, 4)],
                "max": [round(bbox.XMax, 4), round(bbox.YMax, 4), round(bbox.ZMax, 4)],
            },
            "volume_mm3": round(float(self.shape.Volume), 3),
            "surface_area_mm2": round(float(self.shape.Area), 3),
        }

    def get_features(self) -> List[Dict[str, Any]]:
        """Tool: Retrieve all recognized engineering features."""
        return [f.to_dict() for f in self.features]

    def get_feature(self, feature_id: str) -> Optional[Dict[str, Any]]:
        """Tool: Retrieve specific engineering feature details by ID."""
        feat = next((f for f in self.features if f.feature_id == feature_id), None)
        return feat.to_dict() if feat else None

    def get_dimension_candidates(self) -> List[Dict[str, Any]]:
        """Tool: Retrieve all candidate dimensions with raw OCCT values and semantics."""
        return [c.to_dict() for c in self.candidate_set.candidates]

    def get_dimension(self, dimension_id: str) -> Optional[Dict[str, Any]]:
        """Tool: Retrieve a specific dimension candidate by ID."""
        cand = next((c for c in self.candidate_set.candidates if c.id == dimension_id), None)
        return cand.to_dict() if cand else None

    def measure_distance(self, entity_a: str, entity_b: str) -> Dict[str, Any]:
        """Tool: Compute exact Euclidean distance between two B-Rep face entities."""
        face_a = self.engine.face_map.get(entity_a)
        face_b = self.engine.face_map.get(entity_b)
        if not face_a or not face_b:
            return {"status": "error", "message": f"One or both entities not found: {entity_a}, {entity_b}"}
        res = self.engine.measure_thickness(entity_a, entity_b)
        return res.to_dict()

    def measure_angle(self, entity_a: str, entity_b: str) -> Dict[str, Any]:
        """Tool: Compute exact angle between two planar face normals or cylinder axes."""
        face_a = self.engine.face_map.get(entity_a)
        face_b = self.engine.face_map.get(entity_b)
        if not face_a or not face_b:
            return {"status": "error", "message": f"One or both entities not found: {entity_a}, {entity_b}"}
        res = self.engine.measure_angle(entity_a, entity_b)
        return res.to_dict()

    def get_available_views(self) -> Dict[str, List[float]]:
        """Tool: Retrieve standard orthographic drawing views and camera direction vectors."""
        return {name: list(vec) for name, vec in STANDARD_VIEWS.items()}

    def get_view_visibility(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Tool: Retrieve 3D-to-2D projection visibility classification per view."""
        va = next((a for a in self.view_report.analyses if a.candidate_id == candidate_id), None)
        return va.to_dict() if va else None

    def get_datums(self) -> List[Dict[str, Any]]:
        """Tool: Retrieve candidate datum-like reference geometry."""
        return [d.to_dict() for d in self.dep_result.potential_datums]

    def get_dimension_dependencies(self) -> Dict[str, Any]:
        """Tool: Retrieve mathematical dependency graph, additive chains, and derived notes."""
        return self.dep_result.to_dict()

    def get_dimension_coverage(self) -> List[Dict[str, Any]]:
        """Tool: Retrieve feature-by-feature dimensioning completeness status."""
        return [c.to_dict() for c in self.red_result.feature_coverages]

    def get_brep_faces(self) -> List[str]:
        """Tool: Retrieve all valid B-Rep face entity names."""
        return list(self.engine.face_map.keys())
