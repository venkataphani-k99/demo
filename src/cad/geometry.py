"""Deep geometry parameter extraction for FreeCAD / OCCT shapes.

Extracts exact mathematical parameters from B-Rep surfaces and curves:
- Cylindrical surfaces: radius, diameter, axis vector, center point, axial length, sweep angle.
- Planar surfaces: surface normal, origin/point, area, bounding box.
- Toroidal surfaces: major/minor radius, center, axis.
- Circular & linear edges: radius, center, axis, direction vectors.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import FreeCAD
import Part
from src.cad.topology import TopologyGraph


@dataclass
class CylindricalFace:
    id: str
    radius: float
    diameter: float
    axis_direction: List[float]
    axis_position: List[float]
    surface_area: float
    axial_length: float
    angular_sweep_deg: float
    boundary_edges: List[str]
    adjacent_faces: List[str]
    center_of_mass: List[float]
    bounding_box: Dict[str, float]
    is_closed_u: bool
    classification: str = "cylindrical_face"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanarFace:
    id: str
    area: float
    normal: List[float]
    position: List[float]
    boundary_edges: List[str]
    adjacent_faces: List[str]
    center_of_mass: List[float]
    bounding_box: Dict[str, float]
    wire_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToroidalFace:
    id: str
    major_radius: float
    minor_radius: float
    axis_direction: List[float]
    center: List[float]
    area: float
    boundary_edges: List[str]
    adjacent_faces: List[str]
    center_of_mass: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BSplineFace:
    id: str
    area: float
    boundary_edges: List[str]
    adjacent_faces: List[str]
    center_of_mass: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EdgeGeometry:
    id: str
    curve_type: str
    curve_class: str
    length: float
    is_closed: bool
    start_point: Optional[List[float]] = None
    end_point: Optional[List[float]] = None
    circle_radius: Optional[float] = None
    circle_diameter: Optional[float] = None
    circle_center: Optional[List[float]] = None
    circle_axis: Optional[List[float]] = None
    line_direction: Optional[List[float]] = None
    sharing_faces: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_vector(v: FreeCAD.Base.Vector) -> List[float]:
    """Return normalized [x, y, z] float list."""
    mag = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if mag > 1e-12:
        return [float(v.x / mag), float(v.y / mag), float(v.z / mag)]
    return [float(v.x), float(v.y), float(v.z)]


def normalize_curve_type(type_id: str, class_name: str) -> str:
    """Normalize FreeCAD/OCCT curve type identifier to standard engineering terminology."""
    t = type_id.lower()
    c = class_name.lower()
    if "bspline" in t or "bspline" in c:
        return "BSplineCurve"
    elif "bezier" in t or "bezier" in c:
        return "BezierCurve"
    elif "circle" in t or "circle" in c:
        return "Circle"
    elif "ellipse" in t or "ellipse" in c:
        return "Ellipse"
    elif "hyperbola" in t or "hyperbola" in c:
        return "Hyperbola"
    elif "parabola" in t or "parabola" in c:
        return "Parabola"
    elif "line" in t or "line" in c:
        return "Line"
    return class_name or type_id


def extract_cylindrical_face(
    face: Part.Face, face_id: str, topo_graph: TopologyGraph
) -> CylindricalFace:
    """Extract full mathematical parameters for a cylindrical face."""
    surf = face.Surface
    radius = float(surf.Radius)
    diameter = 2.0 * radius

    # Axis vector & Center point
    axis_vec = surf.Axis
    axis_dir = normalize_vector(axis_vec)
    center_pt = surf.Center
    axis_pos = [float(center_pt.x), float(center_pt.y), float(center_pt.z)]

    # Parameter ranges: U is angular (radians), V is axial length
    u_min, u_max, v_min, v_max = face.ParameterRange
    axial_length = float(abs(v_max - v_min))
    angular_sweep_deg = float((abs(u_max - u_min) / math.pi) * 180.0)

    # Center of mass / bounding box
    com = face.CenterOfMass
    com_list = [float(com.x), float(com.y), float(com.z)]

    bbox = face.BoundBox
    bbox_dict = {
        "min_x": float(bbox.XMin),
        "min_y": float(bbox.YMin),
        "min_z": float(bbox.ZMin),
        "max_x": float(bbox.XMax),
        "max_y": float(bbox.YMax),
        "max_z": float(bbox.ZMax),
    }

    # Topology
    f_topo = topo_graph.faces.get(face_id)
    boundary_edges = f_topo.edge_ids if f_topo else []
    adjacent_faces = f_topo.adjacent_face_ids if f_topo else []
    is_closed_u = bool(getattr(surf, "isUClosed", lambda: False)())

    return CylindricalFace(
        id=face_id,
        radius=radius,
        diameter=diameter,
        axis_direction=axis_dir,
        axis_position=axis_pos,
        surface_area=float(face.Area),
        axial_length=axial_length,
        angular_sweep_deg=angular_sweep_deg,
        boundary_edges=boundary_edges,
        adjacent_faces=adjacent_faces,
        center_of_mass=com_list,
        bounding_box=bbox_dict,
        is_closed_u=is_closed_u,
    )


def extract_planar_face(
    face: Part.Face, face_id: str, topo_graph: TopologyGraph
) -> PlanarFace:
    """Extract parameters for a planar face."""
    surf = face.Surface

    # Normal vector
    if hasattr(surf, "Axis"):
        normal_vec = surf.Axis
    else:
        normal_vec = surf.normal(0.0, 0.0)
    normal = normalize_vector(normal_vec)

    # Position
    pos = surf.Position if hasattr(surf, "Position") else surf.Center if hasattr(surf, "Center") else face.CenterOfGravity
    pos_list = [float(pos.x), float(pos.y), float(pos.z)]

    com = face.CenterOfMass
    com_list = [float(com.x), float(com.y), float(com.z)]

    bbox = face.BoundBox
    bbox_dict = {
        "min_x": float(bbox.XMin),
        "min_y": float(bbox.YMin),
        "min_z": float(bbox.ZMin),
        "max_x": float(bbox.XMax),
        "max_y": float(bbox.YMax),
        "max_z": float(bbox.ZMax),
    }

    f_topo = topo_graph.faces.get(face_id)
    boundary_edges = f_topo.edge_ids if f_topo else []
    adjacent_faces = f_topo.adjacent_face_ids if f_topo else []

    return PlanarFace(
        id=face_id,
        area=float(face.Area),
        normal=normal,
        position=pos_list,
        boundary_edges=boundary_edges,
        adjacent_faces=adjacent_faces,
        center_of_mass=com_list,
        bounding_box=bbox_dict,
        wire_count=len(face.Wires),
    )


def extract_toroidal_face(
    face: Part.Face, face_id: str, topo_graph: TopologyGraph
) -> ToroidalFace:
    """Extract parameters for a toroidal face."""
    surf = face.Surface
    major_r = float(getattr(surf, "MajorRadius", 0.0))
    minor_r = float(getattr(surf, "MinorRadius", 0.0))

    axis_vec = getattr(surf, "Axis", FreeCAD.Base.Vector(0, 0, 1))
    axis_dir = normalize_vector(axis_vec)

    center_pt = getattr(surf, "Center", face.CenterOfGravity)
    center = [float(center_pt.x), float(center_pt.y), float(center_pt.z)]

    com = face.CenterOfMass
    com_list = [float(com.x), float(com.y), float(com.z)]

    f_topo = topo_graph.faces.get(face_id)
    boundary_edges = f_topo.edge_ids if f_topo else []
    adjacent_faces = f_topo.adjacent_face_ids if f_topo else []

    return ToroidalFace(
        id=face_id,
        major_radius=major_r,
        minor_radius=minor_r,
        axis_direction=axis_dir,
        center=center,
        area=float(face.Area),
        boundary_edges=boundary_edges,
        adjacent_faces=adjacent_faces,
        center_of_mass=com_list,
    )


def extract_bspline_face(
    face: Part.Face, face_id: str, topo_graph: TopologyGraph
) -> BSplineFace:
    """Extract parameters for a B-spline face."""
    com = face.CenterOfMass
    com_list = [float(com.x), float(com.y), float(com.z)]

    f_topo = topo_graph.faces.get(face_id)
    boundary_edges = f_topo.edge_ids if f_topo else []
    adjacent_faces = f_topo.adjacent_face_ids if f_topo else []

    return BSplineFace(
        id=face_id,
        area=float(face.Area),
        boundary_edges=boundary_edges,
        adjacent_faces=adjacent_faces,
        center_of_mass=com_list,
    )


def extract_edge_geometry(
    edge: Part.Edge, edge_id: str, topo_graph: TopologyGraph
) -> EdgeGeometry:
    """Extract parameters for an edge curve."""
    try:
        curve = edge.Curve
    except Exception:
        curve = None

    type_id = getattr(curve, "TypeId", type(curve).__name__) if curve else "Unknown"
    class_name = type(curve).__name__ if curve else "Unknown"

    if curve is None:
        norm_type = "DegenerateOrUndefined"
    else:
        t = type_id.lower()
        c = class_name.lower()
        if "bspline" in t or "bspline" in c:
            norm_type = "BSplineCurve"
        elif "circle" in t or "circle" in c:
            norm_type = "Circle"
        elif "ellipse" in t or "ellipse" in c:
            norm_type = "Ellipse"
        elif "line" in t or "line" in c:
            norm_type = "Line"
        else:
            norm_type = class_name or type_id

    start_pt: Optional[List[float]] = None
    end_pt: Optional[List[float]] = None
    if len(edge.Vertexes) >= 1:
        p1 = edge.Vertexes[0].Point
        start_pt = [float(p1.x), float(p1.y), float(p1.z)]
    if len(edge.Vertexes) >= 2:
        p2 = edge.Vertexes[-1].Point
        end_pt = [float(p2.x), float(p2.y), float(p2.z)]

    circle_r: Optional[float] = None
    circle_dia: Optional[float] = None
    circle_ctr: Optional[List[float]] = None
    circle_ax: Optional[List[float]] = None
    line_dir: Optional[List[float]] = None

    if norm_type == "Circle" and hasattr(curve, "Radius"):
        circle_r = float(curve.Radius)
        circle_dia = 2.0 * circle_r
        if hasattr(curve, "Center"):
            ctr = curve.Center
            circle_ctr = [float(ctr.x), float(ctr.y), float(ctr.z)]
        if hasattr(curve, "Axis"):
            circle_ax = normalize_vector(curve.Axis)

    elif norm_type == "Line" and start_pt and end_pt:
        dx = end_pt[0] - start_pt[0]
        dy = end_pt[1] - start_pt[1]
        dz = end_pt[2] - start_pt[2]
        mag = math.sqrt(dx * dx + dy * dy + dz * dz)
        if mag > 1e-12:
            line_dir = [dx / mag, dy / mag, dz / mag]

    e_topo = topo_graph.edges.get(edge_id)
    sharing_faces = e_topo.face_ids if e_topo else []

    return EdgeGeometry(
        id=edge_id,
        curve_type=norm_type,
        curve_class=class_name,
        length=float(edge.Length),
        is_closed=bool(edge.isClosed()),
        start_point=start_pt,
        end_point=end_pt,
        circle_radius=circle_r,
        circle_diameter=circle_dia,
        circle_center=circle_ctr,
        circle_axis=circle_ax,
        line_direction=line_dir,
        sharing_faces=sharing_faces,
    )
