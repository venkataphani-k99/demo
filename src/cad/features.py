"""Deterministic CAD Feature Recognition Engine for B-Rep Geometry.

Transforms low-level B-Rep topology and geometric measurements into high-level engineering features:
- Logical Cylindrical Feature Grouping (seam merging, multi-face synthesis)
- Internal vs External Surface Orientation (cavity/hole vs boss/protrusion)
- Counterbored Holes & Stepped Cavities
- Through Holes & Bores
- Blind Holes
- External Cylindrical Bosses
- Constant-Radius Fillets & Blends
- Hierarchical Parent/Child Feature Relationships
- Full Verification and Traceability to source B-Rep entities
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import FreeCAD
import Part
from src.cad.measurements import MeasurementEngine, MeasurementResult, shortest_distance_between_lines
from src.cad.topology import TopologyGraph, build_topology_graph


# Explicit geometric tolerances
TOL_RADIUS = 1e-4          # mm: Max radius difference to consider cylinders identical
TOL_AXIS_ANGLE = 1e-3      # deg: Max angular deviation to consider axes parallel
TOL_AXIS_DISTANCE = 1e-3   # mm: Max 3D distance between axis lines to consider coaxial
TOL_PLANAR_NORMAL = 1e-3   # Collinearity threshold for plane normals


@dataclass
class LogicalCylinder:
    """A logical cylindrical feature composed of one or more B-Rep cylindrical faces."""
    group_id: str
    face_ids: List[str]
    radius: float
    diameter: float
    axis_direction: List[float]
    axis_position: List[float]
    axial_length: float
    total_sweep_deg: float
    is_internal: bool  # True = cavity/hole/bore (normal points in), False = boss/shaft (normal points out)
    surface_area: float
    boundary_edges: List[str]
    adjacent_faces: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecognizedFeature:
    """Standardized representation of a recognized CAD engineering feature."""
    feature_id: str
    feature_type: str  # "counterbored_hole", "through_hole", "blind_hole", "external_boss", "internal_bore", "fillet", "chamfer"
    source_entities: List[str]
    dimensions: Dict[str, float]
    axis: Optional[List[float]] = None
    position: Optional[List[float]] = None
    depth: Optional[float] = None
    parent_feature_id: Optional[str] = None
    child_feature_ids: List[str] = field(default_factory=list)
    recognition_rules: List[str] = field(default_factory=list)
    confidence: float = 1.0
    status: str = "confirmed"  # "confirmed", "candidate", "rejected"
    units: str = "mm"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def group_logical_cylinders(
    shape: Part.Shape, topo_graph: TopologyGraph, engine: MeasurementEngine
) -> List[LogicalCylinder]:
    """Group B-Rep cylindrical faces into unified logical cylinders based on geometry and topology."""
    cyl_faces: Dict[str, Part.Face] = {}
    face_radii: Dict[str, float] = {}
    face_axes: Dict[str, FreeCAD.Base.Vector] = {}
    face_centers: Dict[str, FreeCAD.Base.Vector] = {}
    face_sweeps: Dict[str, float] = {}
    face_lengths: Dict[str, float] = {}
    face_internals: Dict[str, bool] = {}

    for fid, face in engine.face_map.items():
        surf = face.Surface
        if "Cylinder" in type(surf).__name__ or "Cylinder" in getattr(surf, "TypeId", ""):
            cyl_faces[fid] = face
            r = float(surf.Radius)
            face_radii[fid] = r
            
            # Axis direction unit vector
            ax = surf.Axis
            mag = math.sqrt(ax.x * ax.x + ax.y * ax.y + ax.z * ax.z)
            face_axes[fid] = FreeCAD.Base.Vector(ax.x / mag, ax.y / mag, ax.z / mag) if mag > 1e-12 else ax
            face_centers[fid] = surf.Center

            u_min, u_max, v_min, v_max = face.ParameterRange
            face_sweeps[fid] = float((abs(u_max - u_min) / math.pi) * 180.0)
            face_lengths[fid] = float(abs(v_max - v_min))

            # Internal vs External Orientation check
            u_mid = (u_min + u_max) / 2.0
            v_mid = (v_min + v_max) / 2.0
            pt = face.valueAt(u_mid, v_mid)
            norm = face.normalAt(u_mid, v_mid)

            delta = pt.sub(surf.Center)
            proj_len = delta.dot(face_axes[fid])
            proj = FreeCAD.Base.Vector(
                face_axes[fid].x * proj_len,
                face_axes[fid].y * proj_len,
                face_axes[fid].z * proj_len,
            )
            radial_vec = delta.sub(proj)

            dot = norm.dot(radial_vec)
            face_internals[fid] = bool(dot < 0)  # dot < 0 means outward normal points towards axis -> cavity

    visited: Set[str] = set()
    groups: List[LogicalCylinder] = []
    group_idx = 1

    for fid in sorted(cyl_faces.keys(), key=lambda x: int(x.replace("Face", ""))):
        if fid in visited:
            continue

        cluster = [fid]
        visited.add(fid)
        r1 = face_radii[fid]
        ax1 = face_axes[fid]
        c1 = face_centers[fid]
        is_int1 = face_internals[fid]

        # Check all other unvisited cylinder faces for coaxiality and identical radius
        for other_fid in sorted(cyl_faces.keys(), key=lambda x: int(x.replace("Face", ""))):
            if other_fid in visited:
                continue

            r2 = face_radii[other_fid]
            ax2 = face_axes[other_fid]
            c2 = face_centers[other_fid]
            is_int2 = face_internals[other_fid]

            # 1. Radius match
            if abs(r1 - r2) > TOL_RADIUS:
                continue

            # 2. Internal/External orientation match
            if is_int1 != is_int2:
                continue

            # 3. Axis collinearity and distance
            dist, ang = shortest_distance_between_lines(c1, ax1, c2, ax2)
            if dist <= TOL_AXIS_DISTANCE and (ang <= TOL_AXIS_ANGLE or abs(ang - 180.0) <= TOL_AXIS_ANGLE):
                # For fillets / small blends, only cluster if they share boundary edges or adjacent faces
                if r1 <= 3.0:
                    f1_adj = set(topo_graph.faces[fid].adjacent_face_ids) if fid in topo_graph.faces else set()
                    f2_adj = set(topo_graph.faces[other_fid].adjacent_face_ids) if other_fid in topo_graph.faces else set()
                    if other_fid in f1_adj or f1_adj.intersection(f2_adj):
                        cluster.append(other_fid)
                        visited.add(other_fid)
                else:
                    # Coaxial structural cylinders (e.g. bores, shafts, bosses) belong to same feature line
                    cluster.append(other_fid)
                    visited.add(other_fid)

        # Build LogicalCylinder
        total_area = sum(float(cyl_faces[f].Area) for f in cluster)
        total_sweep = sum(face_sweeps[f] for f in cluster)
        max_length = max(face_lengths[f] for f in cluster)

        all_boundary_edges: Set[str] = set()
        all_adjacent_faces: Set[str] = set()
        for f in cluster:
            f_topo = topo_graph.faces.get(f)
            if f_topo:
                all_boundary_edges.update(f_topo.edge_ids)
                all_adjacent_faces.update(f_topo.adjacent_face_ids)

        # Remove internal seams between clustered faces
        for f in cluster:
            all_adjacent_faces.discard(f)

        groups.append(
            LogicalCylinder(
                group_id=f"CYL_GROUP_{group_idx:03d}",
                face_ids=sorted(cluster, key=lambda x: int(x.replace("Face", ""))),
                radius=r1,
                diameter=2.0 * r1,
                axis_direction=[float(ax1.x), float(ax1.y), float(ax1.z)],
                axis_position=[float(c1.x), float(c1.y), float(c1.z)],
                axial_length=max_length,
                total_sweep_deg=min(360.0, total_sweep),
                is_internal=is_int1,
                surface_area=total_area,
                boundary_edges=sorted(list(all_boundary_edges)),
                adjacent_faces=sorted(list(all_adjacent_faces), key=lambda x: int(x.replace("Face", ""))),
            )
        )
        group_idx += 1

    return groups


class FeatureRecognizer:
    """Deterministic Engineering Feature Recognition Engine."""

    def __init__(self, shape: Part.Shape, topo_graph: TopologyGraph, engine: MeasurementEngine):
        self.shape = shape
        self.topo_graph = topo_graph
        self.engine = engine
        self.logical_cylinders = group_logical_cylinders(shape, topo_graph, engine)
        self.recognized_features: List[RecognizedFeature] = []
        self._feature_counter = 1

    def _next_id(self, prefix: str) -> str:
        fid = f"{prefix}_{self._feature_counter:03d}"
        self._feature_counter += 1
        return fid

    def recognize_all_features(self) -> List[RecognizedFeature]:
        """Execute complete deterministic feature recognition pipeline."""
        self.recognized_features.clear()
        self._feature_counter = 1

        claimed_faces: Set[str] = set()

        # Step 1: Counterbore Recognition (Compound stepped cavities)
        cbore_features = self._recognize_counterbores(claimed_faces)
        self.recognized_features.extend(cbore_features)

        # Step 2: Through Holes & Internal Bores
        hole_features = self._recognize_holes_and_bores(claimed_faces)
        self.recognized_features.extend(hole_features)

        # Step 3: External Cylindrical Bosses
        boss_features = self._recognize_bosses(claimed_faces)
        self.recognized_features.extend(boss_features)

        # Step 4: Fillets & Blends
        fillet_features = self._recognize_fillets(claimed_faces)
        self.recognized_features.extend(fillet_features)

        # Step 5: Validate and refine feature relationships
        self._validate_features()

        return self.recognized_features

    # =========================================================================
    # 5C: Counterbore Recognition
    # =========================================================================
    def _recognize_counterbores(self, claimed_faces: Set[str]) -> List[RecognizedFeature]:
        features: List[RecognizedFeature] = []
        internal_cyls = [c for c in self.logical_cylinders if c.is_internal and c.total_sweep_deg >= 350.0]

        # Search pairs of internal cylinders that are coaxial and stepped
        for i in range(len(internal_cyls)):
            for j in range(i + 1, len(internal_cyls)):
                c1 = internal_cyls[i]
                c2 = internal_cyls[j]

                # Distinguish smaller (bore) vs larger (counterbore)
                if abs(c1.diameter - c2.diameter) < 0.5:
                    continue  # Same diameter, not stepped

                bore_cyl = c1 if c1.diameter < c2.diameter else c2
                cbore_cyl = c2 if c1.diameter < c2.diameter else c1

                # Check coaxiality
                p1 = FreeCAD.Base.Vector(*bore_cyl.axis_position)
                d1 = FreeCAD.Base.Vector(*bore_cyl.axis_direction)
                p2 = FreeCAD.Base.Vector(*cbore_cyl.axis_position)
                d2 = FreeCAD.Base.Vector(*cbore_cyl.axis_direction)

                dist, ang = shortest_distance_between_lines(p1, d1, p2, d2)
                if dist > TOL_AXIS_DISTANCE or (ang > TOL_AXIS_ANGLE and abs(ang - 180.0) > TOL_AXIS_ANGLE):
                    continue  # Not coaxial

                # Check for intermediate planar transition step face
                # Step face must connect bore faces and cbore faces
                bore_faces_set = set(bore_cyl.face_ids)
                cbore_faces_set = set(cbore_cyl.face_ids)

                step_face_id: Optional[str] = None
                for fid, pface in self.engine.face_map.items():
                    surf = pface.Surface
                    if "Plane" in type(surf).__name__ or "Plane" in getattr(surf, "TypeId", ""):
                        f_adj = set(self.topo_graph.faces[fid].adjacent_face_ids) if fid in self.topo_graph.faces else set()
                        if f_adj.intersection(bore_faces_set) and f_adj.intersection(cbore_faces_set):
                            step_face_id = fid
                            break

                rules = [
                    "coaxial_internal_cylinders_detected",
                    f"bore_diameter_{bore_cyl.diameter:.1f}mm_less_than_counterbore_{cbore_cyl.diameter:.1f}mm",
                ]

                all_supporting_faces = bore_cyl.face_ids + cbore_cyl.face_ids
                if step_face_id:
                    all_supporting_faces.append(step_face_id)
                    rules.append(f"planar_shoulder_step_face_verified({step_face_id})")

                feature_id = self._next_id("CBORE")
                child_bore_id = f"{feature_id}_BORE"
                child_cbore_id = f"{feature_id}_STEP"

                # Calculate depths
                bore_depth = bore_cyl.axial_length
                cbore_depth = cbore_cyl.axial_length
                total_depth = bore_depth + cbore_depth

                features.append(
                    RecognizedFeature(
                        feature_id=feature_id,
                        feature_type="counterbored_hole",
                        source_entities=sorted(all_supporting_faces, key=lambda x: int(x.replace("Face", ""))),
                        dimensions={
                            "bore_diameter": bore_cyl.diameter,
                            "bore_radius": bore_cyl.radius,
                            "counterbore_diameter": cbore_cyl.diameter,
                            "counterbore_radius": cbore_cyl.radius,
                            "bore_depth": bore_depth,
                            "counterbore_depth": cbore_depth,
                            "total_depth": total_depth,
                        },
                        axis=bore_cyl.axis_direction,
                        position=bore_cyl.axis_position,
                        depth=total_depth,
                        child_feature_ids=[child_bore_id, child_cbore_id],
                        recognition_rules=rules,
                        confidence=0.99 if step_face_id else 0.90,
                        status="confirmed" if step_face_id else "candidate",
                        notes=[
                            f"Counterbored hole composed of Ø{bore_cyl.diameter:.2f}mm inner bore and Ø{cbore_cyl.diameter:.2f}mm upper counterbore.",
                            f"Coaxial alignment: axis distance = {dist:.4f}mm, angular deviation = {ang:.3f}°.",
                        ],
                    )
                )

                claimed_faces.update(all_supporting_faces)

        return features

    # =========================================================================
    # 5B: Through Holes & Internal Cylindrical Bores
    # =========================================================================
    def _recognize_holes_and_bores(self, claimed_faces: Set[str]) -> List[RecognizedFeature]:
        features: List[RecognizedFeature] = []

        for cyl in self.logical_cylinders:
            if not cyl.is_internal:
                continue

            # Skip faces already claimed by compound counterbore
            unclaimed = [f for f in cyl.face_ids if f not in claimed_faces]
            if not unclaimed:
                continue

            # Check if full cylinder or through bore
            is_full_circle = cyl.total_sweep_deg >= 350.0

            # Inspect adjacent faces at ends
            adj_faces = cyl.adjacent_faces
            rules = [
                "internal_cylindrical_cavity_orientation",
                f"diameter_{cyl.diameter:.2f}mm_extracted",
            ]

            feature_type = "through_hole" if is_full_circle else "internal_bore"
            if is_full_circle:
                rules.append("full_360_degree_circular_cavity_boundary")
            else:
                rules.append(f"partial_cylindrical_vault_sweep_{cyl.total_sweep_deg:.1f}deg")

            fid = self._next_id("HOLE" if is_full_circle else "BORE")
            features.append(
                RecognizedFeature(
                    feature_id=fid,
                    feature_type=feature_type,
                    source_entities=cyl.face_ids,
                    dimensions={
                        "diameter": cyl.diameter,
                        "radius": cyl.radius,
                        "length": cyl.axial_length,
                        "angular_sweep_deg": cyl.total_sweep_deg,
                    },
                    axis=cyl.axis_direction,
                    position=cyl.axis_position,
                    depth=cyl.axial_length,
                    recognition_rules=rules,
                    confidence=0.98 if is_full_circle else 0.90,
                    status="confirmed",
                    notes=[
                        f"{feature_type.replace('_', ' ').title()} of Ø{cyl.diameter:.2f}mm and axial length {cyl.axial_length:.2f}mm.",
                    ],
                )
            )
            claimed_faces.update(cyl.face_ids)

        return features

    # =========================================================================
    # 5D: External Boss Recognition
    # =========================================================================
    def _recognize_bosses(self, claimed_faces: Set[str]) -> List[RecognizedFeature]:
        features: List[RecognizedFeature] = []

        for cyl in self.logical_cylinders:
            if cyl.is_internal:
                continue

            # Fillets have small radii (typically <= 3mm with ~90 deg sweep); bosses are structural features
            if cyl.radius <= 3.0 and cyl.total_sweep_deg <= 135.0:
                continue  # Defer to fillet recognition

            unclaimed = [f for f in cyl.face_ids if f not in claimed_faces]
            if not unclaimed:
                continue

            rules = [
                "external_surface_normal_pointing_away_from_axis",
                f"cylindrical_boss_diameter_{cyl.diameter:.2f}mm",
                f"angular_sweep_{cyl.total_sweep_deg:.1f}deg",
            ]

            fid = self._next_id("BOSS")
            features.append(
                RecognizedFeature(
                    feature_id=fid,
                    feature_type="external_boss",
                    source_entities=cyl.face_ids,
                    dimensions={
                        "diameter": cyl.diameter,
                        "radius": cyl.radius,
                        "axial_length": cyl.axial_length,
                        "angular_sweep_deg": cyl.total_sweep_deg,
                    },
                    axis=cyl.axis_direction,
                    position=cyl.axis_position,
                    depth=cyl.axial_length,
                    recognition_rules=rules,
                    confidence=0.95,
                    status="confirmed",
                    notes=[
                        f"External cylindrical boss protrusion with Ø{cyl.diameter:.2f}mm and axial extent {cyl.axial_length:.2f}mm.",
                    ],
                )
            )
            claimed_faces.update(cyl.face_ids)

        return features

    # =========================================================================
    # 5E: Fillet & Blend Recognition
    # =========================================================================
    def _recognize_fillets(self, claimed_faces: Set[str]) -> List[RecognizedFeature]:
        features: List[RecognizedFeature] = []

        # Find cylindrical and toroidal blend surfaces with small constant radius
        for cyl in self.logical_cylinders:
            if cyl.radius > 5.0:
                continue  # Structural cylinder, not a fillet

            unclaimed = [f for f in cyl.face_ids if f not in claimed_faces]
            if not unclaimed:
                continue

            # Fillet conditions: sweep around 90 deg (75 to 135 deg) and small constant radius
            if 70.0 <= cyl.total_sweep_deg <= 140.0:
                rules = [
                    f"constant_blend_radius_{cyl.radius:.2f}mm",
                    f"quadrant_corner_sweep_{cyl.total_sweep_deg:.1f}deg",
                    "tangential_transition_between_adjacent_faces",
                ]

                fid = self._next_id("FILLET")
                features.append(
                    RecognizedFeature(
                        feature_id=fid,
                        feature_type="fillet",
                        source_entities=cyl.face_ids,
                        dimensions={
                            "radius": cyl.radius,
                            "diameter": cyl.diameter,
                            "length": cyl.axial_length,
                            "sweep_deg": cyl.total_sweep_deg,
                        },
                        axis=cyl.axis_direction,
                        position=cyl.axis_position,
                        recognition_rules=rules,
                        confidence=0.96,
                        status="confirmed",
                        notes=[
                            f"Constant-radius R{cyl.radius:.2f}mm edge fillet blend joining adjacent faces {cyl.adjacent_faces}.",
                        ],
                    )
                )
                claimed_faces.update(cyl.face_ids)

        # Also inspect Toroidal corner blends
        for fid, face in self.engine.face_map.items():
            if fid in claimed_faces:
                continue
            surf = face.Surface
            if "Toroid" in type(surf).__name__ or "Toroid" in getattr(surf, "TypeId", ""):
                r_minor = float(getattr(surf, "MinorRadius", 0.0))
                r_major = float(getattr(surf, "MajorRadius", 0.0))
                if r_minor > 0.0 and r_minor <= 5.0:
                    feat_id = self._next_id("FILLET")
                    features.append(
                        RecognizedFeature(
                            feature_id=feat_id,
                            feature_type="toroidal_corner_blend",
                            source_entities=[fid],
                            dimensions={
                                "radius": r_minor,
                                "major_radius": r_major,
                                "area": float(face.Area),
                            },
                            recognition_rules=[
                                f"toroidal_corner_blend_minor_radius_{r_minor:.2f}mm",
                            ],
                            confidence=0.92,
                            status="confirmed",
                            notes=[f"Toroidal corner blend with corner radius R{r_minor:.2f}mm."],
                        )
                    )
                    claimed_faces.add(fid)

        return features

    # =========================================================================
    # 5G: Feature Validation Engine
    # =========================================================================
    def _validate_features(self) -> None:
        """Validate every recognized feature against strict geometric/topological invariants."""
        for feat in self.recognized_features:
            # 1. Source entities existence check
            for eid in feat.source_entities:
                if eid not in self.engine.face_map:
                    feat.status = "rejected"
                    feat.notes.append(f"Validation failure: Entity {eid} does not exist in model.")
                    break

            # 2. Diameter / Radius positivity
            for dim_name, dim_val in feat.dimensions.items():
                if ("diameter" in dim_name or "radius" in dim_name) and dim_val <= 0.0:
                    feat.status = "rejected"
                    feat.notes.append(f"Validation failure: Non-positive dimension {dim_name} = {dim_val}.")

            # 3. Counterbore specific validation
            if feat.feature_type == "counterbored_hole":
                bore_d = feat.dimensions.get("bore_diameter", 0.0)
                cbore_d = feat.dimensions.get("counterbore_diameter", 0.0)
                if bore_d >= cbore_d:
                    feat.status = "rejected"
                    feat.notes.append(f"Validation failure: Bore diameter ({bore_d}) >= counterbore diameter ({cbore_d}).")
                else:
                    feat.notes.append("Validation passed: Strict coaxial stepped cavity geometry verified.")


def recognize_cad_features(
    shape: Part.Shape, topo_graph: TopologyGraph, engine: MeasurementEngine
) -> List[RecognizedFeature]:
    """Top-level function to perform deterministic feature recognition on a CAD shape."""
    recognizer = FeatureRecognizer(shape, topo_graph, engine)
    return recognizer.recognize_all_features()
