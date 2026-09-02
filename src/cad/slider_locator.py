"""Phase M2 — Slider & Lifter Kinematic Locator (Validated & Audited).

Identifies mechanical side-action sliders, lifters, and core pulls with
rigorous mathematical vector validation (S · D_pull = 0) and exact
Three.js rendering coordinate outputs.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.cad.mfg_vector_verifier import ManufacturingVectorVerifier


@dataclass
class SliderAction:
    slider_id: str                      # "SLIDER_001", "LIFTER_001"
    mechanism_type: str                 # "EXTERNAL_SLIDER_CAM", "INTERNAL_LIFTER_ANGLED", "HYDRAULIC_CORE_PULL"
    pull_vector: List[float]            # Normalized orthogonal slide vector [sx, sy, sz]
    arrow_start: List[float]            # [x0, y0, z0] exact cluster anchor
    arrow_end: List[float]              # [x1, y1, z1] exact endpoint
    required_stroke_mm: float           # Clearance travel
    recommended_cam_angle_deg: float    # e.g. 10° - 15°
    source_faces: List[str]             # ["Face12", "Face13"]
    undercut_area_mm2: float
    estimated_tooling_cost_usd: float
    is_eliminatable_via_redesign: bool
    dfm_elimination_advice: str
    vector_verification: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SliderLocator:
    """Calculates slider kinematics and generates verified 3D vector coordinates."""

    def __init__(self, shape: Part.Shape, mold_report: Any):
        self.shape = shape
        self.mold_report = mold_report
        self._faces_map = {f"Face{i+1}": f for i, f in enumerate(shape.Faces)}
        self._bbox = shape.BoundBox
        self._part_center = np.array([
            (self._bbox.XMin + self._bbox.XMax) / 2.0,
            (self._bbox.YMin + self._bbox.YMax) / 2.0,
            (self._bbox.ZMin + self._bbox.ZMax) / 2.0,
        ], dtype=float)

    def locate_sliders(self) -> List[SliderAction]:
        """Locates all side actions and lifters with verified vector mathematics."""
        d_pull = ManufacturingVectorVerifier.normalize(self.mold_report.optimal_pull_direction)
        undercut_face_ids = list(self.mold_report.undercut_faces)

        if not undercut_face_ids:
            return []

        # 1. Cluster adjacent undercut faces into discrete physical mechanisms
        clusters = self._cluster_undercut_faces(undercut_face_ids)

        sliders: List[SliderAction] = []
        for idx, cluster_faces in enumerate(clusters, 1):
            slider = self._build_slider_action(idx, cluster_faces, d_pull)
            sliders.append(slider)

        return sliders

    def _cluster_undercut_faces(self, face_ids: List[str]) -> List[List[str]]:
        """Clusters adjacent undercut faces based on geometric spatial proximity."""
        clusters: List[List[str]] = []
        visited = set()

        centers_map: Dict[str, np.ndarray] = {}
        for fid in face_ids:
            fd = self.mold_report.face_details.get(fid)
            if fd:
                centers_map[fid] = np.array(fd.center, dtype=float)
            else:
                centers_map[fid] = np.array([0.0, 0.0, 0.0])

        for fid in face_ids:
            if fid in visited:
                continue

            current_cluster = [fid]
            visited.add(fid)
            c1 = centers_map[fid]

            for other_fid in face_ids:
                if other_fid in visited:
                    continue

                c2 = centers_map[other_fid]
                if np.linalg.norm(c1 - c2) < 35.0:
                    current_cluster.append(other_fid)
                    visited.add(other_fid)

            clusters.append(current_cluster)

        return clusters[:20]

    def _build_slider_action(
        self,
        index: int,
        cluster_faces: List[str],
        d_pull: np.ndarray,
    ) -> SliderAction:
        """M2.7 & M2.8: Computes strict orthogonal slide vector, exact start/end points, and DFM advice."""
        normals: List[np.ndarray] = []
        centers: List[np.ndarray] = []
        total_area = 0.0

        for fid in cluster_faces:
            fd = self.mold_report.face_details.get(fid)
            if fd:
                total_area += fd.area_mm2
                normals.append(np.array(fd.normal, dtype=float))
                centers.append(np.array(fd.center, dtype=float))

        cluster_center = np.mean(centers, axis=0) if centers else np.array([0.0, 0.0, 0.0])
        mean_normal = np.mean(normals, axis=0) if normals else np.array([1.0, 0.0, 0.0])

        # M2.7 Strict Orthogonal Slide Vector
        slide_vec, ortho_dot = ManufacturingVectorVerifier.compute_orthogonal_slide_vector(
            mean_normal=mean_normal,
            d_pull=d_pull,
            cluster_center=cluster_center,
            part_center=self._part_center,
        )

        # M2.14 Determine Lifter vs External Slider
        from_center_vec = cluster_center - self._part_center
        p_outward = FreeCAD.Vector(float(cluster_center[0]), float(cluster_center[1]), float(cluster_center[2])) + FreeCAD.Vector(float(slide_vec[0]), float(slide_vec[1]), float(slide_vec[2])) * 4.0
        p_inward = FreeCAD.Vector(float(cluster_center[0]), float(cluster_center[1]), float(cluster_center[2])) - FreeCAD.Vector(float(slide_vec[0]), float(slide_vec[1]), float(slide_vec[2])) * 4.0

        is_internal = False
        if hasattr(self.shape, "isInside"):
            if self.shape.isInside(p_outward, 0.1, True) and not self.shape.isInside(p_inward, 0.1, True):
                is_internal = True
                slide_vec = -slide_vec
            elif np.dot(from_center_vec, slide_vec) < 0.0:
                is_internal = True

        stroke = round(max(15.0, math.sqrt(max(1.0, total_area)) + 8.0), 1)
        p0 = cluster_center
        p1 = p0 + slide_vec * stroke

        if is_internal:
            mechanism = "INTERNAL_LIFTER_ANGLED"
            slider_id = f"LIFTER_{index:03d}"
            cam_angle = 12.0
            tooling_cost = 4500.0
            dfm_advice = (
                "Internal Undercut: Requires an angled lifter pulling inward into the part cavity during ejection."
            )
        else:
            mechanism = "EXTERNAL_SLIDER_CAM"
            slider_id = f"SLIDER_{index:03d}"
            cam_angle = 15.0
            tooling_cost = 3500.0
            dfm_advice = (
                "External Undercut: Requires a lateral cam slider or hydraulic core pull. "
                "Evaluate whether a bypass shut-off window can eliminate the mechanism."
            )

        # Vector Verification Proof
        proof = ManufacturingVectorVerifier.verify_vector_pair(
            marker_id=slider_id,
            semantic_type="LIFTER_TRAVEL_VECTOR" if is_internal else "SLIDER_TRAVEL_VECTOR",
            source_faces=cluster_faces,
            origin=[round(float(p0[0]), 2), round(float(p0[1]), 2), round(float(p0[2]), 2)],
            direction=[round(float(slide_vec[0]), 4), round(float(slide_vec[1]), 4), round(float(slide_vec[2]), 4)],
            length_mm=stroke,
            d_pull=d_pull.tolist(),
        ).to_dict()

        return SliderAction(
            slider_id=slider_id,
            mechanism_type=mechanism,
            pull_vector=[round(float(slide_vec[0]), 4), round(float(slide_vec[1]), 4), round(float(slide_vec[2]), 4)],
            arrow_start=[round(float(p0[0]), 2), round(float(p0[1]), 2), round(float(p0[2]), 2)],
            arrow_end=[round(float(p1[0]), 2), round(float(p1[1]), 2), round(float(p1[2]), 2)],
            required_stroke_mm=stroke,
            recommended_cam_angle_deg=cam_angle,
            source_faces=cluster_faces,
            undercut_area_mm2=round(total_area, 2),
            estimated_tooling_cost_usd=tooling_cost,
            is_eliminatable_via_redesign=True,
            dfm_elimination_advice=dfm_advice,
            vector_verification=proof,
        )
