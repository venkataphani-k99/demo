"""Phase 20.1 — Exact B-Rep Geometry Auditor & Assembly Deduplication.

Extracts deterministic OCCT analytical geometry and deduplicates assembly occurrences:
1. Unique B-Rep solid detection (deduplicates identical assembly occurrences by volume, centroid, topology).
2. Global finite bounding box calculation (excluding infinite datum planes).
3. Analytical surface classification (Plane, Cylinder, Cone, Sphere, Torus, BSpline).
4. Analytical curve classification (Line, Circle, Arc, Ellipse, BSpline).
5. Exact geometric metrics (Radii, Diameters, Cylindrical Axes, Extents, Planar Normals, Areas).
6. Pure OCCT geometric truth — zero LLM hallucination.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part


@dataclass
class CylinderMetric:
    face_id: str
    radius: float
    diameter: float
    axis: List[float]
    location: List[float]
    height: float
    is_internal: bool  # True for hole/bore, False for boss/shaft/outer


@dataclass
class PlaneMetric:
    face_id: str
    normal: List[float]
    centroid: List[float]
    area: float


@dataclass
class SolidAudit:
    solid_index: int
    solid_hash: str
    volume_mm3: float
    surface_area_mm2: float
    bbox_extents_mm: List[float]
    face_count: int
    edge_count: int
    vertex_count: int
    is_duplicate: bool
    occurrence_of: Optional[int] = None


@dataclass
class BRepGeometryAudit:
    file_name: str
    total_raw_solids: int
    unique_solids_count: int
    unique_faces_count: int
    unique_edges_count: int
    unique_vertices_count: int
    assembly_envelope_mm: List[float]  # [X, Y, Z]
    envelope_min_point: List[float]    # [Xmin, Ymin, Zmin]
    envelope_max_point: List[float]    # [Xmax, Ymax, Zmax]
    total_volume_cm3: float
    total_surface_area_cm2: float
    surface_types: Dict[str, int]
    curve_types: Dict[str, int]
    cylinders: List[CylinderMetric]
    planes: List[PlaneMetric]
    solids: List[SolidAudit]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BRepGeometryAuditor:
    """Performs deterministic B-Rep geometry audits directly on OpenCASCADE shapes."""

    def audit_shape(self, shape: Any, file_name: str = "model.step") -> BRepGeometryAudit:
        """Audit shape topology, analytical surfaces, and deduplicate assembly solids."""
        if hasattr(shape, "primary_shape") and shape.primary_shape is not None:
            shape = shape.primary_shape
        elif hasattr(shape, "shape"):
            shape = shape.shape

        raw_solids = []
        if hasattr(shape, "Solids") and shape.Solids:
            raw_solids = [s for s in shape.Solids if s.BoundBox.XLength < 1e5 and s.BoundBox.YLength < 1e5]

        if not raw_solids:
            # Wrap as single solid
            raw_solids = [shape]

        # 1. Deduplicate Solids
        unique_solids: List[Part.Shape] = []
        solid_audits: List[SolidAudit] = []
        seen_fingerprints: Dict[str, int] = {}

        for idx, solid in enumerate(raw_solids):
            vol = round(float(solid.Volume), 2)
            area = round(float(solid.Area), 2)
            bb = solid.BoundBox
            extents = [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]
            center = [round((bb.XMin + bb.XMax) / 2.0, 2), round((bb.YMin + bb.YMax) / 2.0, 2), round((bb.ZMin + bb.ZMax) / 2.0, 2)]

            # Fingerprint combines topology count, volume, area, and bounding box center
            fp_str = f"{len(solid.Faces)}_{len(solid.Edges)}_{vol}_{area}_{extents}_{center}"
            fp_hash = hashlib.sha256(fp_str.encode()).hexdigest()[:12]

            is_dup = fp_hash in seen_fingerprints
            occur_of = seen_fingerprints.get(fp_hash)

            if not is_dup:
                seen_fingerprints[fp_hash] = idx + 1
                unique_solids.append(solid)

            solid_audits.append(SolidAudit(
                solid_index=idx + 1,
                solid_hash=fp_hash,
                volume_mm3=vol,
                surface_area_mm2=area,
                bbox_extents_mm=extents,
                face_count=len(solid.Faces),
                edge_count=len(solid.Edges),
                vertex_count=len(solid.Vertexes),
                is_duplicate=is_dup,
                occurrence_of=occur_of,
            ))

        # 2. Compute Unique Assembly Envelope
        combined_bbox = FreeCAD.BoundBox()
        total_vol_mm3 = 0.0
        total_area_mm2 = 0.0
        unique_faces: List[Part.Face] = []
        unique_edges: List[Part.Edge] = []
        unique_vertices: List[Part.Vertex] = []

        for s in unique_solids:
            combined_bbox.add(s.BoundBox)
            total_vol_mm3 += float(s.Volume)
            total_area_mm2 += float(s.Area)
            unique_faces.extend(s.Faces)
            unique_edges.extend(s.Edges)
            unique_vertices.extend(s.Vertexes)

        env_extents = [
            round(max(0.1, combined_bbox.XLength), 3),
            round(max(0.1, combined_bbox.YLength), 3),
            round(max(0.1, combined_bbox.ZLength), 3),
        ]
        env_min = [round(combined_bbox.XMin, 3), round(combined_bbox.YMin, 3), round(combined_bbox.ZMin, 3)]
        env_max = [round(combined_bbox.XMax, 3), round(combined_bbox.YMax, 3), round(combined_bbox.ZMax, 3)]

        # 3. Classify Analytical Surfaces & Extract Metrics
        surface_types: Dict[str, int] = {}
        cylinders: List[CylinderMetric] = []
        planes: List[PlaneMetric] = []

        for f_idx, face in enumerate(unique_faces):
            f_id = f"Face{f_idx + 1}"
            stype = type(face.Surface).__name__.replace("Geom", "")
            surface_types[stype] = surface_types.get(stype, 0) + 1

            if "Cylinder" in stype:
                try:
                    surf = face.Surface
                    rad = round(float(getattr(surf, "Radius", 0.0)), 3)
                    axis_obj = getattr(surf, "Axis", None)
                    axis_vec = [round(axis_obj.x, 3), round(axis_obj.y, 3), round(axis_obj.z, 3)] if axis_obj else [0, 0, 1]
                    loc_obj = getattr(surf, "Center", getattr(surf, "Location", None))
                    loc_vec = [round(loc_obj.x, 3), round(loc_obj.y, 3), round(loc_obj.z, 3)] if loc_obj else [0, 0, 0]
                    f_bbox = face.BoundBox
                    h_val = round(max(f_bbox.XLength, f_bbox.YLength, f_bbox.ZLength), 3)

                    # Determine internal vs external via normal orientation
                    uv_center = face.ParameterRange
                    u_mid = (uv_center[0] + uv_center[1]) / 2.0
                    v_mid = (uv_center[2] + uv_center[3]) / 2.0
                    norm = face.normalAt(u_mid, v_mid)
                    pt = face.valueAt(u_mid, v_mid)
                    center_to_surf = FreeCAD.Vector(pt.x - loc_vec[0], pt.y - loc_vec[1], pt.z - loc_vec[2])
                    dot = norm.dot(center_to_surf)
                    is_internal = dot < 0.0

                    cylinders.append(CylinderMetric(
                        face_id=f_id,
                        radius=rad,
                        diameter=round(rad * 2.0, 3),
                        axis=axis_vec,
                        location=loc_vec,
                        height=h_val,
                        is_internal=is_internal,
                    ))
                except Exception:
                    pass

            elif "Plane" in stype:
                try:
                    uv_center = face.ParameterRange
                    u_mid = (uv_center[0] + uv_center[1]) / 2.0
                    v_mid = (uv_center[2] + uv_center[3]) / 2.0
                    norm = face.normalAt(u_mid, v_mid)
                    cen = face.CenterOfMass
                    planes.append(PlaneMetric(
                        face_id=f_id,
                        normal=[round(norm.x, 3), round(norm.y, 3), round(norm.z, 3)],
                        centroid=[round(cen.x, 3), round(cen.y, 3), round(cen.z, 3)],
                        area=round(float(face.Area), 2),
                    ))
                except Exception:
                    pass

        # 4. Classify Analytical Curves
        curve_types: Dict[str, int] = {}
        for edge in unique_edges:
            try:
                ctype = type(edge.Curve).__name__.replace("Geom", "")
                curve_types[ctype] = curve_types.get(ctype, 0) + 1
            except Exception:
                curve_types["Unknown"] = curve_types.get("Unknown", 0) + 1

        return BRepGeometryAudit(
            file_name=file_name,
            total_raw_solids=len(raw_solids),
            unique_solids_count=len(unique_solids),
            unique_faces_count=len(unique_faces),
            unique_edges_count=len(unique_edges),
            unique_vertices_count=len(unique_vertices),
            assembly_envelope_mm=env_extents,
            envelope_min_point=env_min,
            envelope_max_point=env_max,
            total_volume_cm3=round(total_vol_mm3 / 1000.0, 2),
            total_surface_area_cm2=round(total_area_mm2 / 100.0, 2),
            surface_types=surface_types,
            curve_types=curve_types,
            cylinders=cylinders,
            planes=planes,
            solids=solid_audits,
        )
