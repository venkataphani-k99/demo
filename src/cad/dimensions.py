"""Deterministic Dimension Candidate Engine for CAD Intelligence.

Generates a structured, fully traceable set of dimension candidates
from recognized engineering features and B-Rep geometry.

Every numeric value originates from deterministic FreeCAD/OCCT geometry.
No values are estimated from images, pixels, SVG, or LLM reasoning.

Candidate types:
    diameter    - circular/cylindrical feature diameter
    radius      - fillet/blend radius
    linear      - distance between parallel planes, feature lengths, overall extents
    depth       - hole / bore / counterbore depth
    angle       - angle between faces or feature axes (when engineering-meaningful)

Status vocabulary:
    valid       - confirmed by exact B-Rep measurement
    candidate   - plausible but not fully verified by topology invariants
    ambiguous   - multiple references compete; reason stored
    rejected    - failed validation invariant
    unsupported - geometry exists but semantic meaning cannot be determined
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import FreeCAD

from src.cad.features import RecognizedFeature
from src.cad.measurements import MeasurementEngine, MeasurementResult
from src.cad.topology import TopologyGraph


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionCandidate:
    """A single engineering dimension candidate.

    Every field is traceable to B-Rep geometry; no field is estimated.
    """
    id: str                                   # "D001", "D002", …
    type: str                                 # "diameter", "radius", "linear", "depth", "angle"
    value: float                              # raw numeric value (mm or deg)
    unit: str                                 # "mm" or "deg"
    formatted_value: str                      # e.g. "Ø5.500 mm", "R2.000 mm", "50.000 mm"
    source_entities: List[str]                # B-Rep face/edge IDs contributing to this dim
    source_feature: Optional[str]             # feature_id from recognized features, or None
    measurement_method: str                   # OCCT calculation method used
    status: str                               # "valid" | "candidate" | "ambiguous" | "rejected" | "unsupported"
    dimension_semantics: str                  # "feature_size" | "feature_depth" | "overall_extent" | "feature_spacing" | "blend_radius"
    preferred_view: Optional[str] = None      # will be assigned in view analysis phase
    alternative_views: List[str] = field(default_factory=list)
    feature_group: Optional[str] = None       # grouping key for repeated equivalent features (e.g. "FILLET_R2")
    reason: Optional[str] = None              # explanation for ambiguous/rejected status
    axis: Optional[List[float]] = None        # feature axis vector, for view analysis
    position: Optional[List[float]] = None    # representative 3D position of feature
    details: Dict[str, Any] = field(default_factory=dict)  # supplemental metadata

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionCandidateSet:
    """Container for all dimension candidates generated from one model."""
    model_file: str
    total: int
    valid: int
    ambiguous: int
    rejected: int
    unsupported: int
    candidates: List[DimensionCandidate]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_file": self.model_file,
            "total": self.total,
            "valid": self.valid,
            "ambiguous": self.ambiguous,
            "rejected": self.rejected,
            "unsupported": self.unsupported,
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dimension ID counter
# ─────────────────────────────────────────────────────────────────────────────

class _DimIdGen:
    def __init__(self, prefix: str = "D"):
        self._n = 0
        self._prefix = prefix

    def next(self) -> str:
        self._n += 1
        return f"{self._prefix}{self._n:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Tolerances for duplicate detection
# ─────────────────────────────────────────────────────────────────────────────
TOL_DIM_MATCH = 1e-3   # mm: consider two dimensions identical if within this


def _round(v: float, ndigits: int = 6) -> float:
    return round(v, ndigits)


def _fmt_diameter(v: float, unit: str = "mm") -> str:
    return f"Ø{v:.3f} {unit}"


def _fmt_radius(v: float, unit: str = "mm") -> str:
    return f"R{v:.3f} {unit}"


def _fmt_linear(v: float, unit: str = "mm") -> str:
    return f"{v:.3f} {unit}"


def _fmt_angle(v: float) -> str:
    return f"{v:.2f}°"


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class DimensionCandidateEngine:
    """Generates deterministic engineering dimension candidates.

    Sources:
      - Recognized engineering features (Phase 5)
      - Exact measurement engine (Phase 4)
      - B-Rep planar face geometry
      - Model bounding box
    """

    def __init__(
        self,
        features: List[RecognizedFeature],
        engine: MeasurementEngine,
        topo_graph: TopologyGraph,
        model_file: str = "",
    ):
        self._features = features
        self._engine = engine
        self._topo = topo_graph
        self._model_file = model_file
        self._id_gen = _DimIdGen()
        self._candidates: List[DimensionCandidate] = []

    def generate(self) -> DimensionCandidateSet:
        """Execute full candidate generation pipeline."""
        self._candidates = []

        # 7B: Diameter candidates from cylindrical features
        self._generate_diameter_candidates()

        # 7C: Radius candidates from fillet features (with dedup)
        self._generate_radius_candidates()

        # 7D: Linear dimension candidates
        self._generate_linear_candidates()

        # 7F: Depth candidates from counterbores / holes
        self._generate_depth_candidates()

        # 7E: Angular candidates (only where engineering meaning is clear)
        self._generate_angular_candidates()

        # Count by status
        statuses = [c.status for c in self._candidates]
        return DimensionCandidateSet(
            model_file=self._model_file,
            total=len(self._candidates),
            valid=statuses.count("valid"),
            ambiguous=statuses.count("ambiguous"),
            rejected=statuses.count("rejected"),
            unsupported=statuses.count("unsupported"),
            candidates=self._candidates,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 7B — Diameter Candidates
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_diameter_candidates(self) -> None:
        """Create diameter candidates from all recognized cylindrical features."""
        diameter_feature_types = {
            "counterbored_hole",
            "through_hole",
            "internal_bore",
            "external_boss",
        }

        for feat in self._features:
            ftype = feat.feature_type

            if ftype == "counterbored_hole":
                # Two diameters: bore and counterbore
                # source_entities contains all faces; bore faces are index 0,1 and cbore faces are index 2,3
                bore_entities = feat.source_entities[:2]
                cbore_entities = feat.source_entities[2:4] if len(feat.source_entities) >= 4 else feat.source_entities[:2]
                self._add_diameter(
                    value=feat.dimensions["bore_diameter"],
                    entities=bore_entities,
                    source_feature=feat.feature_id,
                    semantics="feature_size",
                    axis=feat.axis,
                    position=feat.position,
                    method="cylindrical_surface_diameter",
                    details={"role": "bore_diameter", "counterbore_parent": feat.feature_id},
                )
                self._add_diameter(
                    value=feat.dimensions["counterbore_diameter"],
                    entities=cbore_entities,
                    source_feature=feat.feature_id,
                    semantics="feature_size",
                    axis=feat.axis,
                    position=feat.position,
                    method="cylindrical_surface_diameter",
                    details={"role": "counterbore_diameter", "counterbore_parent": feat.feature_id},
                )

            elif ftype in ("through_hole", "internal_bore"):
                self._add_diameter(
                    value=feat.dimensions["diameter"],
                    entities=feat.source_entities,
                    source_feature=feat.feature_id,
                    semantics="feature_size",
                    axis=feat.axis,
                    position=feat.position,
                    method="cylindrical_surface_diameter",
                    details={"feature_type": ftype},
                )

            elif ftype == "external_boss":
                self._add_diameter(
                    value=feat.dimensions["diameter"],
                    entities=feat.source_entities,
                    source_feature=feat.feature_id,
                    semantics="feature_size",
                    axis=feat.axis,
                    position=feat.position,
                    method="cylindrical_surface_diameter",
                    details={"feature_type": "external_boss"},
                )

    def _add_diameter(
        self,
        value: float,
        entities: List[str],
        source_feature: str,
        semantics: str,
        axis: Optional[List[float]],
        position: Optional[List[float]],
        method: str,
        details: Dict[str, Any],
    ) -> None:
        # Validate source entities exist
        missing = [e for e in entities if e not in self._engine.face_map]
        if missing:
            self._candidates.append(DimensionCandidate(
                id=self._id_gen.next(),
                type="diameter",
                value=_round(value),
                unit="mm",
                formatted_value=_fmt_diameter(value),
                source_entities=entities,
                source_feature=source_feature,
                measurement_method=method,
                status="rejected",
                dimension_semantics=semantics,
                axis=axis,
                position=position,
                reason=f"Source entities not found in model: {missing}",
                details=details,
            ))
            return

        if value <= 0:
            self._candidates.append(DimensionCandidate(
                id=self._id_gen.next(),
                type="diameter",
                value=_round(value),
                unit="mm",
                formatted_value=_fmt_diameter(value),
                source_entities=entities,
                source_feature=source_feature,
                measurement_method=method,
                status="rejected",
                dimension_semantics=semantics,
                reason="Non-positive diameter",
                details=details,
            ))
            return

        self._candidates.append(DimensionCandidate(
            id=self._id_gen.next(),
            type="diameter",
            value=_round(value),
            unit="mm",
            formatted_value=_fmt_diameter(value),
            source_entities=entities,
            source_feature=source_feature,
            measurement_method=method,
            status="valid",
            dimension_semantics=semantics,
            axis=axis,
            position=position,
            details=details,
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # 7C — Radius Candidates (with deduplication)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_radius_candidates(self) -> None:
        """Generate grouped radius candidates for fillet/blend features."""
        fillet_types = {"fillet", "toroidal_corner_blend"}
        fillet_feats = [f for f in self._features if f.feature_type in fillet_types]

        if not fillet_feats:
            return

        # Group fillets by radius value (within tolerance)
        radius_groups: Dict[float, List[RecognizedFeature]] = {}
        for feat in fillet_feats:
            r = feat.dimensions.get("radius", 0.0)
            matched_key: Optional[float] = None
            for key in radius_groups:
                if abs(r - key) <= TOL_DIM_MATCH:
                    matched_key = key
                    break
            if matched_key is None:
                radius_groups[r] = [feat]
            else:
                radius_groups[matched_key].append(feat)

        for radius_val, group_feats in sorted(radius_groups.items()):
            # Collect all source entities from the group
            all_entities: List[str] = []
            for f in group_feats:
                for e in f.source_entities:
                    if e not in all_entities:
                        all_entities.append(e)

            group_key = f"FILLET_R{radius_val:.3f}"
            feat_ids = [f.feature_id for f in group_feats]
            count = len(group_feats)

            self._candidates.append(DimensionCandidate(
                id=self._id_gen.next(),
                type="radius",
                value=_round(radius_val),
                unit="mm",
                formatted_value=_fmt_radius(radius_val),
                source_entities=all_entities,
                source_feature=feat_ids[0] if len(feat_ids) == 1 else None,
                measurement_method="cylindrical_surface_radius",
                status="valid",
                dimension_semantics="blend_radius",
                feature_group=group_key,
                axis=group_feats[0].axis,
                details={
                    "fillet_count": count,
                    "source_features": feat_ids,
                    "note": f"Represents {count} fillet/blend instances with R={radius_val:.3f}mm",
                },
            ))

    # ─────────────────────────────────────────────────────────────────────────
    # 7D — Linear Dimension Candidates
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_linear_candidates(self) -> None:
        """Generate linear dimension candidates from:
        - Parallel planar face distances (thicknesses)
        - Model bounding box overall extents
        - Feature axial lengths
        """
        self._generate_planar_thickness_candidates()
        self._generate_overall_extents()
        self._generate_feature_axial_lengths()

    def _generate_planar_thickness_candidates(self) -> None:
        """Detect parallel planar face pairs and generate thickness candidates."""
        # Build list of planar faces with their normals
        planar_faces: List[Tuple[str, List[float], List[float]]] = []
        for fid, face in self._engine.face_map.items():
            surf = face.Surface
            if "Plane" in type(surf).__name__ or "Plane" in getattr(surf, "TypeId", ""):
                n = surf.Axis  # plane normal
                mag = math.sqrt(n.x**2 + n.y**2 + n.z**2)
                if mag > 1e-9:
                    normal = [n.x / mag, n.y / mag, n.z / mag]
                    pos = [float(surf.Position.x), float(surf.Position.y), float(surf.Position.z)]
                    planar_faces.append((fid, normal, pos))

        # Find pairs with anti-parallel or parallel normals (same axis, opposite sides)
        checked: Set[Tuple[str, str]] = set()
        for i, (fid_a, n_a, p_a) in enumerate(planar_faces):
            for j, (fid_b, n_b, p_b) in enumerate(planar_faces):
                if i >= j:
                    continue
                pair_key = (min(fid_a, fid_b), max(fid_a, fid_b))
                if pair_key in checked:
                    continue

                # Check anti-parallel normals (parallel planes facing each other)
                dot = sum(n_a[k] * n_b[k] for k in range(3))
                if abs(abs(dot) - 1.0) > 1e-3:
                    continue  # not parallel

                # Measure thickness
                result = self._engine.measure_thickness(fid_a, fid_b)
                if result.status != "valid" or result.value <= 0.01:
                    continue

                checked.add(pair_key)

                # Determine semantic
                value = result.value
                semantics = self._classify_linear_semantics(fid_a, fid_b, n_a, value)

                self._candidates.append(DimensionCandidate(
                    id=self._id_gen.next(),
                    type="linear",
                    value=_round(value),
                    unit="mm",
                    formatted_value=_fmt_linear(value),
                    source_entities=[fid_a, fid_b],
                    source_feature=None,
                    measurement_method="parallel_plane_perpendicular_distance",
                    status="valid",
                    dimension_semantics=semantics,
                    axis=[float(n_a[0]), float(n_a[1]), float(n_a[2])],
                    details={
                        "face_a": fid_a,
                        "face_b": fid_b,
                        "normal": [_round(x) for x in n_a],
                    },
                ))

    def _classify_linear_semantics(self, fid_a: str, fid_b: str, normal: List[float], value: float) -> str:
        """Classify the engineering meaning of a planar distance."""
        bb = self._engine.shape.BoundBox
        # If the distance matches overall bounding box extent in that direction -> overall_extent
        for bbox_len in [bb.XLength, bb.YLength, bb.ZLength]:
            if abs(value - bbox_len) < 0.5:
                return "overall_extent"
        return "thickness"

    def _generate_overall_extents(self) -> None:
        """Generate overall model size candidates from bounding box."""
        bb = self._engine.shape.BoundBox

        extents = [
            ("X", bb.XLength, bb.XMin, bb.XMax),
            ("Y", bb.YLength, bb.YMin, bb.YMax),
            ("Z", bb.ZLength, bb.ZMin, bb.ZMax),
        ]

        # Axes as 3D vectors
        axis_vectors = {
            "X": [1.0, 0.0, 0.0],
            "Y": [0.0, 1.0, 0.0],
            "Z": [0.0, 0.0, 1.0],
        }

        for axis_name, length, vmin, vmax in extents:
            if length <= 0.01:
                continue

            # Check if a planar-face pair already covers this extent — avoid dupe
            already_covered = any(
                c.type == "linear"
                and abs(c.value - length) < TOL_DIM_MATCH
                and c.dimension_semantics in ("overall_extent", "thickness")
                for c in self._candidates
            )

            self._candidates.append(DimensionCandidate(
                id=self._id_gen.next(),
                type="linear",
                value=_round(length),
                unit="mm",
                formatted_value=_fmt_linear(length),
                source_entities=[],  # bounding box — no single face pair
                source_feature=None,
                measurement_method="brep_bounding_box_extent",
                status="valid" if not already_covered else "candidate",
                dimension_semantics="overall_extent",
                axis=axis_vectors[axis_name],
                reason="Covered by planar thickness measurement" if already_covered else None,
                details={
                    "axis": axis_name,
                    "min": _round(vmin),
                    "max": _round(vmax),
                    "note": f"Overall model extent in {axis_name} direction",
                },
            ))

    def _generate_feature_axial_lengths(self) -> None:
        """Generate axial-length candidates for holes, bores, and bosses."""
        for feat in self._features:
            ftype = feat.feature_type

            if ftype == "through_hole":
                length = feat.dimensions.get("length", 0.0)
                if length > 0.01:
                    self._candidates.append(DimensionCandidate(
                        id=self._id_gen.next(),
                        type="linear",
                        value=_round(length),
                        unit="mm",
                        formatted_value=_fmt_linear(length),
                        source_entities=feat.source_entities,
                        source_feature=feat.feature_id,
                        measurement_method="cylindrical_face_axial_extent",
                        status="valid",
                        dimension_semantics="feature_length",
                        axis=feat.axis,
                        position=feat.position,
                        details={"role": "through_hole_length"},
                    ))

            elif ftype == "external_boss":
                length = feat.dimensions.get("axial_length", 0.0)
                if length > 0.01:
                    self._candidates.append(DimensionCandidate(
                        id=self._id_gen.next(),
                        type="linear",
                        value=_round(length),
                        unit="mm",
                        formatted_value=_fmt_linear(length),
                        source_entities=feat.source_entities,
                        source_feature=feat.feature_id,
                        measurement_method="cylindrical_face_axial_extent",
                        status="valid",
                        dimension_semantics="feature_length",
                        axis=feat.axis,
                        position=feat.position,
                        details={"role": "boss_axial_length"},
                    ))

            elif ftype == "internal_bore" and feat.dimensions.get("angular_sweep_deg", 360) < 180:
                # Partial bore (like the arched ceiling vault) - ambiguous depth
                length = feat.dimensions.get("length", 0.0)
                if length > 0.01:
                    self._candidates.append(DimensionCandidate(
                        id=self._id_gen.next(),
                        type="linear",
                        value=_round(length),
                        unit="mm",
                        formatted_value=_fmt_linear(length),
                        source_entities=feat.source_entities,
                        source_feature=feat.feature_id,
                        measurement_method="cylindrical_face_axial_extent",
                        status="ambiguous",
                        dimension_semantics="feature_length",
                        axis=feat.axis,
                        position=feat.position,
                        reason=f"Partial bore sweep ({feat.dimensions.get('angular_sweep_deg', 0):.1f}°) — length ambiguous",
                        details={"role": "partial_bore_length"},
                    ))

    # ─────────────────────────────────────────────────────────────────────────
    # 7F — Depth Candidates (holes / counterbores)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_depth_candidates(self) -> None:
        for feat in self._features:
            ftype = feat.feature_type

            if ftype == "counterbored_hole":
                bore_depth = feat.dimensions.get("bore_depth", 0.0)
                cbore_depth = feat.dimensions.get("counterbore_depth", 0.0)
                total_depth = feat.dimensions.get("total_depth", 0.0)

                for depth_name, depth_val, role in [
                    ("bore_depth", bore_depth, "bore_depth"),
                    ("counterbore_depth", cbore_depth, "counterbore_depth"),
                    ("total_depth", total_depth, "total_depth"),
                ]:
                    if depth_val > 0.01:
                        self._candidates.append(DimensionCandidate(
                            id=self._id_gen.next(),
                            type="depth",
                            value=_round(depth_val),
                            unit="mm",
                            formatted_value=_fmt_linear(depth_val),
                            source_entities=feat.source_entities,
                            source_feature=feat.feature_id,
                            measurement_method="cylindrical_face_axial_extent",
                            status="valid",
                            dimension_semantics="feature_depth",
                            axis=feat.axis,
                            position=feat.position,
                            details={
                                "role": role,
                                "parent_feature": feat.feature_id,
                            },
                        ))

    # ─────────────────────────────────────────────────────────────────────────
    # 7E — Angular Candidates
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_angular_candidates(self) -> None:
        """Generate angle candidates only for engineering-meaningful cases."""
        # The main engineering-significant angular relationship in Pieza18_1 is
        # the perpendicularity between the vertical bore axis and the horizontal bore axis.
        # This is derived from exact cylinder axis geometry.

        # Collect internal cylindrical features with their axes
        internal_cyls = [
            f for f in self._features
            if f.feature_type in ("counterbored_hole", "through_hole", "internal_bore")
            and f.axis is not None
        ]

        checked_pairs: Set[Tuple[str, str]] = set()
        for i, feat_a in enumerate(internal_cyls):
            for j, feat_b in enumerate(internal_cyls):
                if i >= j:
                    continue
                pair_key = (feat_a.feature_id, feat_b.feature_id)
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                ax_a = feat_a.axis
                ax_b = feat_b.axis
                if ax_a is None or ax_b is None:
                    continue

                # Angle between axes
                mag_a = math.sqrt(sum(x**2 for x in ax_a))
                mag_b = math.sqrt(sum(x**2 for x in ax_b))
                if mag_a < 1e-9 or mag_b < 1e-9:
                    continue

                dot = sum(ax_a[k] / mag_a * ax_b[k] / mag_b for k in range(3))
                dot = max(-1.0, min(1.0, dot))
                angle_deg = math.degrees(math.acos(abs(dot)))  # 0..90 range

                # Only report engineering-significant angles (near 0° or 90°)
                is_perp = abs(angle_deg - 90.0) < 0.5
                is_parallel = angle_deg < 0.5

                if is_perp or is_parallel:
                    semantics = "perpendicularity" if is_perp else "parallelism"
                    formatted = _fmt_angle(angle_deg)
                    self._candidates.append(DimensionCandidate(
                        id=self._id_gen.next(),
                        type="angle",
                        value=_round(angle_deg),
                        unit="deg",
                        formatted_value=formatted,
                        source_entities=feat_a.source_entities + feat_b.source_entities,
                        source_feature=None,
                        measurement_method="cylinder_axis_angle",
                        status="valid",
                        dimension_semantics=semantics,
                        details={
                            "feature_a": feat_a.feature_id,
                            "feature_b": feat_b.feature_id,
                            "axis_a": [_round(x) for x in ax_a],
                            "axis_b": [_round(x) for x in ax_b],
                            "note": f"{semantics} between {feat_a.feature_id} and {feat_b.feature_id}",
                        },
                    ))
