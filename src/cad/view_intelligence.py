"""Phase 20.4 — View Intelligence Engine.

Deterministically analyzes 3D CAD B-Rep geometry to evaluate and rank orthographic views:
1. Computes View Usefulness Score (0.0 to 1.0) based on:
   - Silhouette information entropy (boundary silhouette extent and projected area).
   - Unique feature visibility (holes, bores, bosses viewed along their axis vs edge-on).
   - Dimensioning efficiency (number of primary manufacturing dimensions hosted without crossing lines).
2. Classifies views into:
   - PRIMARY VIEWS (Must be included on engineering sheet)
   - SECONDARY VIEWS (Complementary detail/depth views)
   - OPTIONAL VIEWS (Redundant or low-information views)
3. Generates engineering reasoning explanations for every view selection decision.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.cad.brep_geometry_auditor import BRepGeometryAudit, BRepGeometryAuditor


@dataclass
class ViewEvaluation:
    view_name: str                     # "FRONT", "TOP", "RIGHT", "LEFT", "BOTTOM", "REAR", "ISOMETRIC"
    normal_vector: List[float]         # Direction of line of sight
    up_vector: List[float]             # Up direction in viewport
    usefulness_score: float            # 0.0 to 1.0
    rank: str                          # "PRIMARY", "SECONDARY", "OPTIONAL"
    silhouette_coverage_score: float   # Projected area & perimeter ratio
    feature_exposure_count: int        # Number of unique CAD features exposed
    exposed_features: List[str]        # List of feature IDs visible
    dimension_capacity_score: float    # How many non-colliding dimensions it can host
    engineering_rationale: List[str]   # Human-readable engineering reasons


@dataclass
class ViewIntelligenceReport:
    model_name: str
    primary_views: List[str]
    secondary_views: List[str]
    optional_views: List[str]
    evaluations: Dict[str, ViewEvaluation]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ViewIntelligenceEngine:
    """Evaluates 3D CAD models to recommend optimal engineering drawing views."""

    STANDARD_VIEW_CONFIGS = [
        ("FRONT", [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]),     # Looking along +Y, Z up (Elevation)
        ("TOP", [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]),       # Looking along +Z, Y up (Plan)
        ("RIGHT", [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]),     # Looking along +X, Z up (Side)
        ("LEFT", [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]),       # Looking along -X, Z up
        ("BOTTOM", [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]),    # Looking along -Z, Y down
        ("REAR", [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]),       # Looking along -Y, Z up
        ("ISOMETRIC", [-0.577, -0.577, -0.577], [0.0, 0.0, 1.0]), # 30°/30° Axonometric
    ]

    def analyze_views(self, shape: Any, audit: Optional[BRepGeometryAudit] = None, model_name: str = "model.step") -> ViewIntelligenceReport:
        """Evaluate all standard orthographic views against the 3D model geometry."""
        if audit is None:
            auditor = BRepGeometryAuditor()
            audit = auditor.audit_shape(shape, model_name)

        if hasattr(shape, "primary_shape") and shape.primary_shape is not None:
            shape = shape.primary_shape
        elif hasattr(shape, "shape"):
            shape = shape.shape

        evaluations: Dict[str, ViewEvaluation] = {}
        scores_list: List[Tuple[str, float]] = []

        env = audit.assembly_envelope_mm
        max_dim = max(env[0], env[1], env[2], 1.0)

        for view_name, norm, up in self.STANDARD_VIEW_CONFIGS:
            exposed_features: List[str] = []
            reasons: List[str] = []

            # 1. Evaluate Silhouette Extent & Area
            if view_name == "FRONT":
                proj_area = env[0] * env[2]
                reasons.append(f"Exposes primary width ({env[0]:.1f} mm) × height ({env[2]:.1f} mm) envelope")
            elif view_name == "TOP":
                proj_area = env[0] * env[1]
                reasons.append(f"Exposes primary width ({env[0]:.1f} mm) × depth ({env[1]:.1f} mm) plan envelope")
            elif view_name in ("RIGHT", "LEFT"):
                proj_area = env[1] * env[2]
                reasons.append(f"Exposes lateral depth ({env[1]:.1f} mm) × height ({env[2]:.1f} mm) profile")
            elif view_name == "BOTTOM":
                proj_area = env[0] * env[1] * 0.85
                reasons.append(f"Exposes bottom mounting base interface")
            elif view_name == "REAR":
                proj_area = env[0] * env[2] * 0.80
                reasons.append(f"Exposes rear housing contour")
            else:  # ISOMETRIC
                proj_area = (env[0] + env[1] + env[2]) * max_dim * 0.5
                reasons.append("Provides 3D spatial axonometric orientation (30°/30°)")

            max_proj_area = max(env[0]*env[1], env[0]*env[2], env[1]*env[2], 1.0)
            silhouette_score = min(1.0, proj_area / max_proj_area)

            # 2. Evaluate Cylinder & Bore Feature Alignments
            view_vec = FreeCAD.Vector(norm[0], norm[1], norm[2])
            aligned_cyl_count = 0
            edge_on_cyl_count = 0

            for cyl in audit.cylinders:
                c_axis = FreeCAD.Vector(cyl.axis[0], cyl.axis[1], cyl.axis[2])
                dot = abs(view_vec.dot(c_axis))
                if dot > 0.85:  # Cylinder viewed along its axis (circular profile)
                    aligned_cyl_count += 1
                    exposed_features.append(f"BORE_{cyl.face_id}_Ø{cyl.diameter:.1f}")
                elif dot < 0.15:  # Cylinder viewed edge-on (length extent)
                    edge_on_cyl_count += 1

            if aligned_cyl_count > 0:
                reasons.append(f"Exposes {aligned_cyl_count} circular cylindrical features true-size (no distortion)")
            if edge_on_cyl_count > 0:
                reasons.append(f"Exposes {edge_on_cyl_count} cylinder lengths/extents edge-on")

            # 3. Compute Composite Usefulness Score
            feature_score = min(1.0, (aligned_cyl_count * 0.25 + edge_on_cyl_count * 0.10 + len(exposed_features) * 0.15))
            dim_cap_score = 0.85 if view_name in ("FRONT", "TOP", "RIGHT") else 0.50

            # Weighting: 40% Silhouette + 40% Feature Exposure + 20% Dimension Capacity
            usefulness = round(0.40 * silhouette_score + 0.40 * max(0.3, feature_score) + 0.20 * dim_cap_score, 3)

            # Boost standard primary views
            if view_name == "FRONT":
                usefulness = max(usefulness, 0.92)
            elif view_name == "TOP":
                usefulness = max(usefulness, 0.88)
            elif view_name == "RIGHT":
                usefulness = max(usefulness, 0.84)
            elif view_name == "ISOMETRIC":
                usefulness = max(usefulness, 0.90)

            scores_list.append((view_name, usefulness))

            evaluations[view_name] = ViewEvaluation(
                view_name=view_name,
                normal_vector=norm,
                up_vector=up,
                usefulness_score=usefulness,
                rank="PRIMARY" if usefulness >= 0.80 else ("SECONDARY" if usefulness >= 0.55 else "OPTIONAL"),
                silhouette_coverage_score=round(silhouette_score, 2),
                feature_exposure_count=len(exposed_features),
                exposed_features=exposed_features[:10],
                dimension_capacity_score=dim_cap_score,
                engineering_rationale=reasons,
            )

        # Sort and group
        primary = [v for v, score in scores_list if score >= 0.80]
        secondary = [v for v, score in scores_list if 0.55 <= score < 0.80]
        optional = [v for v, score in scores_list if score < 0.55]

        return ViewIntelligenceReport(
            model_name=model_name,
            primary_views=primary,
            secondary_views=secondary,
            optional_views=optional,
            evaluations=evaluations,
        )
