"""Exact CAD Measurement Engine for B-Rep Geometry.

Provides deterministic mathematical calculations directly from FreeCAD / OpenCASCADE geometry:
- Point-to-point Euclidean distance
- Edge curve length
- Face area (single face or compound feature)
- Solid volume and total surface area
- Cylinder radius and diameter (single face or multi-face assemblies)
- Cylinder-to-cylinder axis relationships (coaxiality, perpendicularity, axis distance, angle)
- Angle between planar normals, cylinder axes, linear edges, or 3D vectors
- Perpendicular thickness between parallel planar faces
- B-Rep minimum distance between arbitrary topological shapes
- Full traceability to source B-Rep entity IDs
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import FreeCAD
import Part


@dataclass
class MeasurementResult:
    """Standardized contract for all engineering CAD measurements."""
    type: str
    value: float
    unit: str
    raw_value: float
    source_entities: List[str]
    method: str
    status: str = "valid"  # "valid", "invalid", "unsupported"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert measurement to serializable dictionary."""
        return asdict(self)


def _vec_to_list(v: FreeCAD.Base.Vector) -> List[float]:
    return [float(v.x), float(v.y), float(v.z)]


def _normalize(v: FreeCAD.Base.Vector) -> FreeCAD.Base.Vector:
    mag = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if mag > 1e-12:
        return FreeCAD.Base.Vector(v.x / mag, v.y / mag, v.z / mag)
    return FreeCAD.Base.Vector(v.x, v.y, v.z)


def shortest_distance_between_lines(
    p1: FreeCAD.Base.Vector, d1: FreeCAD.Base.Vector,
    p2: FreeCAD.Base.Vector, d2: FreeCAD.Base.Vector
) -> Tuple[float, float]:
    """Calculate shortest 3D distance and angle (degrees) between two infinite lines.
    
    Line 1: L1(t1) = p1 + t1 * d1
    Line 2: L2(t2) = p2 + t2 * d2
    """
    u1 = _normalize(d1)
    u2 = _normalize(d2)

    # Angle between directions
    dot = max(-1.0, min(1.0, u1.x * u2.x + u1.y * u2.y + u1.z * u2.z))
    angle_rad = math.acos(abs(dot))  # angle between lines (0 to 90 deg)
    angle_deg = math.degrees(angle_rad)

    # Cross product of directions
    cx = u1.y * u2.z - u1.z * u2.y
    cy = u1.z * u2.x - u1.x * u2.z
    cz = u1.x * u2.y - u1.y * u2.x
    cross_len = math.sqrt(cx * cx + cy * cy + cz * cz)

    dx = p2.x - p1.x
    dy = p2.y - p1.y
    dz = p2.z - p1.z

    if cross_len < 1e-7:
        # Lines are parallel: distance is length of delta projected orthogonal to u1
        proj_len = dx * u1.x + dy * u1.y + dz * u1.z
        perp_x = dx - proj_len * u1.x
        perp_y = dy - proj_len * u1.y
        perp_z = dz - proj_len * u1.z
        dist = math.sqrt(perp_x * perp_x + perp_y * perp_y + perp_z * perp_z)
        return float(dist), float(angle_deg)
    else:
        # Lines are skew or intersecting: distance is |delta . (u1 x u2)| / |u1 x u2|
        dist = abs(dx * cx + dy * cy + dz * cz) / cross_len
        return float(dist), float(angle_deg)


class MeasurementEngine:
    """Deterministic CAD Measurement Engine operating on FreeCAD TopoShapes."""

    def __init__(self, shape: Part.Shape, units: str = "mm"):
        if shape is None or shape.isNull():
            raise ValueError("MeasurementEngine requires a valid, non-null Part.Shape.")
        self.shape = shape
        self.units = units

        # Build index maps for fast O(1) B-Rep entity lookup
        self.face_map: Dict[str, Part.Face] = {
            f"Face{i + 1}": f for i, f in enumerate(shape.Faces)
        }
        self.edge_map: Dict[str, Part.Edge] = {
            f"Edge{i + 1}": e for i, e in enumerate(shape.Edges)
        }
        self.vertex_map: Dict[str, Part.Vertex] = {
            f"Vertex{i + 1}": v for i, v in enumerate(shape.Vertexes)
        }

    def _resolve_point(self, pt_or_id: Union[str, List[float], Tuple[float, float, float], FreeCAD.Base.Vector]) -> FreeCAD.Base.Vector:
        """Resolve a 3D point from Vertex ID, coordinates list, or Vector."""
        if isinstance(pt_or_id, str):
            if pt_or_id in self.vertex_map:
                p = self.vertex_map[pt_or_id].Point
                return FreeCAD.Base.Vector(p.x, p.y, p.z)
            elif pt_or_id in self.face_map:
                com = self.face_map[pt_or_id].CenterOfMass
                return FreeCAD.Base.Vector(com.x, com.y, com.z)
            else:
                raise KeyError(f"Entity '{pt_or_id}' not found in model.")
        elif isinstance(pt_or_id, FreeCAD.Base.Vector):
            return pt_or_id
        elif isinstance(pt_or_id, (list, tuple)) and len(pt_or_id) == 3:
            return FreeCAD.Base.Vector(float(pt_or_id[0]), float(pt_or_id[1]), float(pt_or_id[2]))
        raise ValueError(f"Cannot resolve point from input: {pt_or_id}")

    # =========================================================================
    # 1. Point-to-Point Distance
    # =========================================================================
    def measure_point_to_point(
        self,
        pt_a: Union[str, List[float], Tuple[float, float, float], FreeCAD.Base.Vector],
        pt_b: Union[str, List[float], Tuple[float, float, float], FreeCAD.Base.Vector],
    ) -> MeasurementResult:
        """Calculate Euclidean distance between two 3D points or vertices."""
        try:
            p1 = self._resolve_point(pt_a)
            p2 = self._resolve_point(pt_b)
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            dz = p2.z - p1.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            srcs = []
            if isinstance(pt_a, str):
                srcs.append(pt_a)
            if isinstance(pt_b, str):
                srcs.append(pt_b)

            return MeasurementResult(
                type="point_to_point",
                value=dist,
                unit=self.units,
                raw_value=dist,
                source_entities=srcs,
                method="euclidean_distance",
                status="valid",
                details={
                    "point_a": _vec_to_list(p1),
                    "point_b": _vec_to_list(p2),
                    "delta": [dx, dy, dz],
                },
            )
        except Exception as e:
            return MeasurementResult(
                type="point_to_point",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[str(pt_a), str(pt_b)],
                method="euclidean_distance",
                status="invalid",
                details={"error": str(e)},
            )

    # =========================================================================
    # 2. Edge Length
    # =========================================================================
    def measure_edge_length(self, edge_id: str) -> MeasurementResult:
        """Calculate exact length of an edge curve."""
        if edge_id not in self.edge_map:
            return MeasurementResult(
                type="edge_length",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[edge_id],
                method="brep_edge_length",
                status="invalid",
                details={"error": f"Edge '{edge_id}' not found."},
            )

        edge = self.edge_map[edge_id]
        length = float(edge.Length)
        curve = edge.Curve
        ctype = type(curve).__name__ if curve else "Unknown"

        return MeasurementResult(
            type="edge_length",
            value=length,
            unit=self.units,
            raw_value=length,
            source_entities=[edge_id],
            method="brep_edge_length",
            status="valid",
            details={"curve_type": ctype, "is_closed": bool(edge.isClosed())},
        )

    # =========================================================================
    # 3. Face Area
    # =========================================================================
    def measure_face_area(self, face_ids: Union[str, List[str]]) -> MeasurementResult:
        """Calculate total surface area of one or more B-Rep faces."""
        if isinstance(face_ids, str):
            face_list = [face_ids]
        else:
            face_list = list(face_ids)

        total_area = 0.0
        missing = []
        individual_areas = {}

        for fid in face_list:
            if fid in self.face_map:
                a = float(self.face_map[fid].Area)
                total_area += a
                individual_areas[fid] = a
            else:
                missing.append(fid)

        if missing:
            return MeasurementResult(
                type="face_area",
                value=0.0,
                unit=f"{self.units}²",
                raw_value=0.0,
                source_entities=face_list,
                method="brep_face_area",
                status="invalid",
                details={"error": f"Faces not found: {missing}"},
            )

        return MeasurementResult(
            type="face_area",
            value=total_area,
            unit=f"{self.units}²",
            raw_value=total_area,
            source_entities=face_list,
            method="brep_face_area",
            status="valid",
            details={"individual_areas": individual_areas, "face_count": len(face_list)},
        )

    # =========================================================================
    # 4. Solid Volume & Total Surface Area
    # =========================================================================
    def measure_solid_volume(self, solid_index: int = 0) -> MeasurementResult:
        """Calculate exact 3D volume of the solid."""
        if not self.shape.Solids:
            return MeasurementResult(
                type="solid_volume",
                value=0.0,
                unit=f"{self.units}³",
                raw_value=0.0,
                source_entities=[],
                method="brep_solid_volume",
                status="invalid",
                details={"error": "Model contains no 3D solids."},
            )

        if solid_index >= len(self.shape.Solids):
            return MeasurementResult(
                type="solid_volume",
                value=0.0,
                unit=f"{self.units}³",
                raw_value=0.0,
                source_entities=[],
                method="brep_solid_volume",
                status="invalid",
                details={"error": f"Solid index {solid_index} out of range."},
            )

        solid = self.shape.Solids[solid_index]
        vol = float(solid.Volume)

        return MeasurementResult(
            type="solid_volume",
            value=vol,
            unit=f"{self.units}³",
            raw_value=vol,
            source_entities=[f"Solid{solid_index + 1}"],
            method="brep_solid_volume",
            status="valid",
            details={"center_of_mass": _vec_to_list(solid.CenterOfMass)},
        )

    def measure_total_surface_area(self) -> MeasurementResult:
        """Calculate total exterior surface area of the model."""
        area = float(self.shape.Area)
        return MeasurementResult(
            type="total_surface_area",
            value=area,
            unit=f"{self.units}²",
            raw_value=area,
            source_entities=list(self.face_map.keys()),
            method="brep_total_surface_area",
            status="valid",
            details={"total_faces": len(self.face_map)},
        )

    # =========================================================================
    # 5. Bounding Box Dimensions
    # =========================================================================
    def measure_bounding_box(self) -> MeasurementResult:
        """Measure bounding box overall dimensions and coordinate extrema."""
        bbox = self.shape.BoundBox
        lx = float(bbox.XLength)
        ly = float(bbox.YLength)
        lz = float(bbox.ZLength)

        return MeasurementResult(
            type="bounding_box",
            value=max(lx, ly, lz),
            unit=self.units,
            raw_value=max(lx, ly, lz),
            source_entities=list(self.face_map.keys()),
            method="brep_bounding_box",
            status="valid",
            details={
                "length_x": lx,
                "length_y": ly,
                "length_z": lz,
                "min_point": [float(bbox.XMin), float(bbox.YMin), float(bbox.ZMin)],
                "max_point": [float(bbox.XMax), float(bbox.YMax), float(bbox.ZMax)],
            },
        )

    # =========================================================================
    # 6. Cylinder Radius & Diameter
    # =========================================================================
    def measure_cylinder_radius(self, face_ids: Union[str, List[str]]) -> MeasurementResult:
        """Measure radius of a single cylindrical face or compound coaxial cylindrical feature."""
        if isinstance(face_ids, str):
            face_list = [face_ids]
        else:
            face_list = list(face_ids)

        if not face_list:
            return MeasurementResult(
                type="radius",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[],
                method="cylindrical_surface_radius",
                status="invalid",
                details={"error": "No face IDs provided."},
            )

        radii = []
        axes = []
        centers = []
        for fid in face_list:
            if fid not in self.face_map:
                return MeasurementResult(
                    type="radius",
                    value=0.0,
                    unit=self.units,
                    raw_value=0.0,
                    source_entities=face_list,
                    method="cylindrical_surface_radius",
                    status="invalid",
                    details={"error": f"Face '{fid}' not found."},
                )

            face = self.face_map[fid]
            surf = face.Surface
            if "Cylinder" not in type(surf).__name__ and "Cylinder" not in getattr(surf, "TypeId", ""):
                return MeasurementResult(
                    type="radius",
                    value=0.0,
                    unit=self.units,
                    raw_value=0.0,
                    source_entities=face_list,
                    method="cylindrical_surface_radius",
                    status="invalid",
                    details={"error": f"Face '{fid}' is not a cylindrical surface (type: {type(surf).__name__})."},
                )

            radii.append(float(surf.Radius))
            axes.append(_normalize(surf.Axis))
            centers.append(surf.Center)

        # Check radius consistency across all faces
        first_r = radii[0]
        for r in radii[1:]:
            if abs(r - first_r) > 1e-4:
                return MeasurementResult(
                    type="radius",
                    value=first_r,
                    unit=self.units,
                    raw_value=first_r,
                    source_entities=face_list,
                    method="cylindrical_surface_radius",
                    status="invalid",
                    details={"error": f"Radii mismatch across selected faces: {radii}"},
                )

        # Check coaxiality across all faces if multiple
        if len(face_list) > 1:
            first_ax = axes[0]
            first_c = centers[0]
            for ax, c in zip(axes[1:], centers[1:]):
                dist, ang = shortest_distance_between_lines(first_c, first_ax, c, ax)
                if dist > 1e-3 or (ang > 1e-2 and abs(ang - 180.0) > 1e-2):
                    return MeasurementResult(
                        type="radius",
                        value=first_r,
                        unit=self.units,
                        raw_value=first_r,
                        source_entities=face_list,
                        method="cylindrical_surface_radius",
                        status="invalid",
                        details={"error": f"Faces are not coaxial (axis dist: {dist:.4f} mm, angle: {ang:.2f}°)"},
                    )

        return MeasurementResult(
            type="radius",
            value=first_r,
            unit=self.units,
            raw_value=first_r,
            source_entities=face_list,
            method="cylindrical_surface_radius",
            status="valid",
            details={
                "radius": first_r,
                "axis_direction": _vec_to_list(axes[0]),
                "axis_position": _vec_to_list(centers[0]),
                "face_count": len(face_list),
            },
        )

    def measure_cylinder_diameter(self, face_ids: Union[str, List[str]]) -> MeasurementResult:
        """Measure diameter of a single cylindrical face or compound coaxial cylindrical feature."""
        res = self.measure_cylinder_radius(face_ids)
        if res.status != "valid":
            res.type = "diameter"
            return res

        dia = res.raw_value * 2.0
        return MeasurementResult(
            type="diameter",
            value=dia,
            unit=self.units,
            raw_value=dia,
            source_entities=res.source_entities,
            method="cylindrical_surface_diameter",
            status="valid",
            details={
                "diameter": dia,
                "radius": res.raw_value,
                "axis_direction": res.details.get("axis_direction"),
                "axis_position": res.details.get("axis_position"),
                "face_count": len(res.source_entities),
            },
        )

    # =========================================================================
    # 7. Cylinder-to-Cylinder Relationships (Coaxiality, Distance, Angle)
    # =========================================================================
    def measure_cylinder_relationship(
        self,
        cyl_a: Union[str, List[str]],
        cyl_b: Union[str, List[str]],
    ) -> MeasurementResult:
        """Measure spatial relationship between two cylinders (axis distance, angle, coaxiality)."""
        res_a = self.measure_cylinder_radius(cyl_a)
        res_b = self.measure_cylinder_radius(cyl_b)

        if res_a.status != "valid" or res_b.status != "valid":
            return MeasurementResult(
                type="cylinder_relationship",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=res_a.source_entities + res_b.source_entities,
                method="cylinder_axis_relationship",
                status="invalid",
                details={
                    "error": "One or both cylinder inputs are invalid.",
                    "details_a": res_a.details,
                    "details_b": res_b.details,
                },
            )

        p1 = FreeCAD.Base.Vector(*res_a.details["axis_position"])
        d1 = FreeCAD.Base.Vector(*res_a.details["axis_direction"])
        p2 = FreeCAD.Base.Vector(*res_b.details["axis_position"])
        d2 = FreeCAD.Base.Vector(*res_b.details["axis_direction"])

        dist, angle_deg = shortest_distance_between_lines(p1, d1, p2, d2)
        is_coaxial = dist < 1e-4 and (angle_deg < 1e-3 or abs(angle_deg - 180.0) < 1e-3)
        is_parallel = (angle_deg < 1e-3 or abs(angle_deg - 180.0) < 1e-3)
        is_perpendicular = abs(angle_deg - 90.0) < 1e-3

        return MeasurementResult(
            type="cylinder_relationship",
            value=dist,
            unit=self.units,
            raw_value=dist,
            source_entities=res_a.source_entities + res_b.source_entities,
            method="cylinder_axis_relationship",
            status="valid",
            details={
                "axis_distance": dist,
                "angle_degrees": angle_deg,
                "is_coaxial": is_coaxial,
                "is_parallel": is_parallel,
                "is_perpendicular": is_perpendicular,
                "radius_a": res_a.raw_value,
                "radius_b": res_b.raw_value,
            },
        )

    # =========================================================================
    # 8. Angle Measurement (Planes, Cylinders, Edges, Vectors)
    # =========================================================================
    def measure_angle(
        self,
        entity_a: Union[str, List[float], FreeCAD.Base.Vector],
        entity_b: Union[str, List[float], FreeCAD.Base.Vector],
    ) -> MeasurementResult:
        """Measure 3D angle (degrees) between two planar face normals, cylinder axes, linear edges, or vectors."""
        def get_direction(ent) -> Tuple[FreeCAD.Base.Vector, str]:
            if isinstance(ent, (list, tuple)) and len(ent) == 3:
                return _normalize(FreeCAD.Base.Vector(ent[0], ent[1], ent[2])), "vector"
            elif isinstance(ent, FreeCAD.Base.Vector):
                return _normalize(ent), "vector"
            elif isinstance(ent, str):
                if ent in self.face_map:
                    f = self.face_map[ent]
                    surf = f.Surface
                    if "Plane" in type(surf).__name__ or "Plane" in getattr(surf, "TypeId", ""):
                        n = surf.Axis if hasattr(surf, "Axis") else surf.normal(0, 0)
                        return _normalize(n), f"plane_normal({ent})"
                    elif "Cylinder" in type(surf).__name__ or "Cylinder" in getattr(surf, "TypeId", ""):
                        return _normalize(surf.Axis), f"cylinder_axis({ent})"
                    else:
                        raise ValueError(f"Face '{ent}' is neither planar nor cylindrical.")
                elif ent in self.edge_map:
                    e = self.edge_map[ent]
                    c = e.Curve
                    if "Line" in type(c).__name__ or "Line" in getattr(c, "TypeId", ""):
                        p1 = e.Vertexes[0].Point
                        p2 = e.Vertexes[-1].Point
                        return _normalize(p2.sub(p1)), f"line_direction({ent})"
                    else:
                        raise ValueError(f"Edge '{ent}' is not a straight line.")
            raise ValueError(f"Cannot resolve direction for entity: {ent}")

        try:
            d1, desc1 = get_direction(entity_a)
            d2, desc2 = get_direction(entity_b)

            dot = max(-1.0, min(1.0, d1.dot(d2)))
            angle_rad = math.acos(dot)
            angle_deg = math.degrees(angle_rad)

            srcs = []
            if isinstance(entity_a, str):
                srcs.append(entity_a)
            if isinstance(entity_b, str):
                srcs.append(entity_b)

            return MeasurementResult(
                type="angle",
                value=angle_deg,
                unit="deg",
                raw_value=angle_deg,
                source_entities=srcs,
                method="vector_angle",
                status="valid",
                details={
                    "direction_a": _vec_to_list(d1),
                    "direction_b": _vec_to_list(d2),
                    "desc_a": desc1,
                    "desc_b": desc2,
                    "angle_rad": angle_rad,
                    "supplementary_angle_deg": 180.0 - angle_deg,
                },
            )
        except Exception as e:
            return MeasurementResult(
                type="angle",
                value=0.0,
                unit="deg",
                raw_value=0.0,
                source_entities=[str(entity_a), str(entity_b)],
                method="vector_angle",
                status="invalid",
                details={"error": str(e)},
            )

    # =========================================================================
    # 9. Thickness / Distance Between Parallel Planar Faces
    # =========================================================================
    def measure_thickness(self, face_a: str, face_b: str) -> MeasurementResult:
        """Measure perpendicular distance (thickness) between two parallel planar faces."""
        if face_a not in self.face_map or face_b not in self.face_map:
            return MeasurementResult(
                type="thickness",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[face_a, face_b],
                method="parallel_plane_perpendicular_distance",
                status="invalid",
                details={"error": f"One or both faces not found: {[face_a, face_b]}"},
            )

        f1 = self.face_map[face_a]
        f2 = self.face_map[face_b]

        s1 = f1.Surface
        s2 = f2.Surface

        if ("Plane" not in type(s1).__name__ and "Plane" not in getattr(s1, "TypeId", "")) or \
           ("Plane" not in type(s2).__name__ and "Plane" not in getattr(s2, "TypeId", "")):
            return MeasurementResult(
                type="thickness",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[face_a, face_b],
                method="parallel_plane_perpendicular_distance",
                status="invalid",
                details={"error": "Both faces must be planar surfaces."},
            )

        n1 = _normalize(s1.Axis if hasattr(s1, "Axis") else s1.normal(0, 0))
        n2 = _normalize(s2.Axis if hasattr(s2, "Axis") else s2.normal(0, 0))

        # Check parallelism (|n1 . n2| == 1.0)
        dot = abs(n1.dot(n2))
        if abs(dot - 1.0) > 1e-4:
            return MeasurementResult(
                type="thickness",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[face_a, face_b],
                method="parallel_plane_perpendicular_distance",
                status="invalid",
                details={
                    "error": "Planes are not parallel.",
                    "normal_dot_product": dot,
                },
            )

        # Perpendicular distance: |(p2 - p1) . n1|
        p1 = s1.Position if hasattr(s1, "Position") else s1.Center if hasattr(s1, "Center") else f1.CenterOfMass
        p2 = s2.Position if hasattr(s2, "Position") else s2.Center if hasattr(s2, "Center") else f2.CenterOfMass

        delta = p2.sub(p1)
        thickness = abs(delta.dot(n1))

        return MeasurementResult(
            type="thickness",
            value=thickness,
            unit=self.units,
            raw_value=thickness,
            source_entities=[face_a, face_b],
            method="parallel_plane_perpendicular_distance",
            status="valid",
            details={
                "thickness": thickness,
                "normal": _vec_to_list(n1),
                "is_opposing": bool(n1.dot(n2) < 0),
            },
        )

    # =========================================================================
    # 10. General B-Rep Distance Between Topological Entities
    # =========================================================================
    def measure_distance(self, entity_a: str, entity_b: str) -> MeasurementResult:
        """Measure exact minimum 3D Euclidean distance between any two B-Rep shapes."""
        def get_shape(ent_id: str) -> Optional[Part.Shape]:
            if ent_id in self.face_map:
                return self.face_map[ent_id]
            elif ent_id in self.edge_map:
                return self.edge_map[ent_id]
            elif ent_id in self.vertex_map:
                return self.vertex_map[ent_id]
            return None

        s1 = get_shape(entity_a)
        s2 = get_shape(entity_b)

        if s1 is None or s2 is None:
            return MeasurementResult(
                type="distance",
                value=0.0,
                unit=self.units,
                raw_value=0.0,
                source_entities=[entity_a, entity_b],
                method="brep_minimum_distance",
                status="invalid",
                details={"error": f"One or both entities not found: {[entity_a, entity_b]}"},
            )

        dist_res = s1.distToShape(s2)
        min_dist = float(dist_res[0])

        return MeasurementResult(
            type="distance",
            value=min_dist,
            unit=self.units,
            raw_value=min_dist,
            source_entities=[entity_a, entity_b],
            method="brep_minimum_distance",
            status="valid",
            details={"minimum_distance": min_dist},
        )
