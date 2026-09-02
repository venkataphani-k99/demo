"""B-Rep shape 3D mesh, wireframe, and full topology exporter for Three.js WebGL visualization.

Extracts complete B-Rep face and edge metadata, preserving exact FreeCAD/OCCT topology
identities (Face1..FaceN, Edge1..EdgeN) for 3D viewport raycasting and inspection.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part
from src.cad.step_loader import load_step


def extract_mesh_from_shape(
    shape: Part.Shape,
    tolerance: float = 0.2,
) -> Dict[str, Any]:
    """Extract 3D triangulated mesh, sharp boundary edges, and complete B-Rep topology."""
    # 1. Global Tessellation
    pts, facets = shape.tessellate(tolerance)
    vertices: List[float] = []
    for p in pts:
        vertices.extend([round(float(p.x), 4), round(float(p.y), 4), round(float(p.z), 4)])

    indices: List[int] = []
    for f in facets:
        indices.extend([int(f[0]), int(f[1]), int(f[2])])

    # 2. Extract Discrete Feature Edges & Full Edge Topology Map
    edges_list: List[List[float]] = []
    edges_map: Dict[str, Dict[str, Any]] = {}

    for e_idx, edge in enumerate(shape.Edges, 1):
        edge_id = f"Edge{e_idx}"
        disc_segs: List[List[float]] = []
        try:
            disc_pts = edge.discretize(Deflection=tolerance)
            if len(disc_pts) >= 2:
                for i in range(len(disc_pts) - 1):
                    p1 = disc_pts[i]
                    p2 = disc_pts[i + 1]
                    seg = [
                        round(float(p1.x), 4), round(float(p1.y), 4), round(float(p1.z), 4),
                        round(float(p2.x), 4), round(float(p2.y), 4), round(float(p2.z), 4),
                    ]
                    edges_list.append(seg)
                    disc_segs.append(seg)
        except Exception:
            pass

        # Identify curve type
        curve_type = "Unknown"
        curve_radius = None
        try:
            curve = edge.Curve
            type_id = getattr(curve, "TypeId", type(curve).__name__)
            t_low = type_id.lower()
            if "circle" in t_low:
                curve_type = "Circle"
                if hasattr(curve, "Radius"):
                    curve_radius = round(float(curve.Radius), 3)
            elif "line" in t_low:
                curve_type = "Line"
            elif "bspline" in t_low:
                curve_type = "BSplineCurve"
            elif "ellipse" in t_low:
                curve_type = "Ellipse"
            elif "bezier" in t_low:
                curve_type = "BezierCurve"
            else:
                curve_type = type_id
        except Exception:
            curve_type = "DegenerateOrUndefined"

        edges_map[edge_id] = {
            "edge_id": edge_id,
            "curve_type": curve_type,
            "length": round(float(edge.Length), 3),
            "radius": curve_radius,
            "is_closed": bool(edge.isClosed()),
            "segments": disc_segs,
            "parent_faces": [],
        }

    # 3. Extract Per-Face B-Rep mappings with exact Surface Classification
    faces_map: Dict[str, Dict[str, Any]] = {}
    for idx, face in enumerate(shape.Faces, 1):
        face_id = f"Face{idx}"
        f_verts: List[float] = []
        f_idx: List[int] = []
        try:
            f_pts, f_facets = face.tessellate(tolerance)
            for p in f_pts:
                f_verts.extend([round(float(p.x), 4), round(float(p.y), 4), round(float(p.z), 4)])
            for f in f_facets:
                f_idx.extend([int(f[0]), int(f[1]), int(f[2])])
        except Exception:
            pass

        # Center of mass
        try:
            cog = face.CenterOfMass
            center = [round(float(cog.x), 3), round(float(cog.y), 3), round(float(cog.z), 3)]
        except Exception:
            center = [0.0, 0.0, 0.0]

        # Surface classification
        surface_type = "Unknown"
        surf_radius = None
        try:
            surf = face.Surface
            stype_id = getattr(surf, "TypeId", type(surf).__name__)
            st_low = stype_id.lower()
            if "plane" in st_low:
                surface_type = "Plane"
            elif "cylinder" in st_low:
                surface_type = "Cylinder"
                if hasattr(surf, "Radius"):
                    surf_radius = round(float(surf.Radius), 3)
            elif "cone" in st_low:
                surface_type = "Cone"
            elif "sphere" in st_low:
                surface_type = "Sphere"
                if hasattr(surf, "Radius"):
                    surf_radius = round(float(surf.Radius), 3)
            elif "torus" in st_low or "toroid" in st_low:
                surface_type = "Toroid"
            elif "bspline" in st_low:
                surface_type = "BSplineSurface"
            elif "bezier" in st_low:
                surface_type = "BezierSurface"
            elif "revolution" in st_low:
                surface_type = "SurfaceOfRevolution"
            elif "extrusion" in st_low:
                surface_type = "SurfaceOfExtrusion"
            else:
                surface_type = stype_id
        except Exception:
            surface_type = "Unknown"

        # Surface Normal calculation
        normal = None
        try:
            if surface_type == "Plane" and hasattr(face.Surface, "Axis"):
                ax = face.Surface.Axis
                mag = math.sqrt(ax.x * ax.x + ax.y * ax.y + ax.z * ax.z)
                if mag > 1e-6:
                    normal = [round(float(ax.x / mag), 4), round(float(ax.y / mag), 4), round(float(ax.z / mag), 4)]
            else:
                u_mid = (face.ParameterRange[0] + face.ParameterRange[1]) / 2.0
                v_mid = (face.ParameterRange[2] + face.ParameterRange[3]) / 2.0
                n = face.normalAt(u_mid, v_mid)
                mag = math.sqrt(n.x * n.x + n.y * n.y + n.z * n.z)
                if mag > 1e-6:
                    normal = [round(float(n.x / mag), 4), round(float(n.y / mag), 4), round(float(n.z / mag), 4)]
        except Exception:
            normal = None

        # Boundary edge identification
        boundary_edges: List[str] = []
        try:
            for f_edge in face.Edges:
                for e_idx, g_edge in enumerate(shape.Edges, 1):
                    if f_edge.isSame(g_edge):
                        e_key = f"Edge{e_idx}"
                        boundary_edges.append(e_key)
                        if e_key in edges_map and face_id not in edges_map[e_key]["parent_faces"]:
                            edges_map[e_key]["parent_faces"].append(face_id)
                        break
        except Exception:
            pass

        faces_map[face_id] = {
            "face_id": face_id,
            "surface_type": surface_type,
            "area": round(float(face.Area), 3),
            "radius": surf_radius,
            "center": center,
            "normal": normal,
            "boundary_edges": boundary_edges,
            "vertices": f_verts,
            "indices": f_idx,
        }

    # 4. Bounding Box & Center
    bbox = shape.BoundBox
    SENTINEL = 1e90

    if abs(bbox.XMin) >= SENTINEL or abs(bbox.XMax) >= SENTINEL:
        if vertices:
            xs = vertices[0::3]; ys = vertices[1::3]; zs = vertices[2::3]
            x_min_v = min(xs); x_max_v = max(xs)
            y_min_v = min(ys); y_max_v = max(ys)
            z_min_v = min(zs); z_max_v = max(zs)
        else:
            x_min_v = x_max_v = y_min_v = y_max_v = z_min_v = z_max_v = 0.0
        center = [
            round((x_min_v + x_max_v) / 2.0, 4),
            round((y_min_v + y_max_v) / 2.0, 4),
            round((z_min_v + z_max_v) / 2.0, 4),
        ]
        bounds = {
            "x_min": round(x_min_v, 4), "x_max": round(x_max_v, 4),
            "y_min": round(y_min_v, 4), "y_max": round(y_max_v, 4),
            "z_min": round(z_min_v, 4), "z_max": round(z_max_v, 4),
            "x_len": round(x_max_v - x_min_v, 4),
            "y_len": round(y_max_v - y_min_v, 4),
            "z_len": round(z_max_v - z_min_v, 4),
            "center": center,
        }
    else:
        center = [
            round(float((bbox.XMin + bbox.XMax) / 2.0), 4),
            round(float((bbox.YMin + bbox.YMax) / 2.0), 4),
            round(float((bbox.ZMin + bbox.ZMax) / 2.0), 4),
        ]
        bounds = {
            "x_min": round(float(bbox.XMin), 4), "x_max": round(float(bbox.XMax), 4),
            "y_min": round(float(bbox.YMin), 4), "y_max": round(float(bbox.YMax), 4),
            "z_min": round(float(bbox.ZMin), 4), "z_max": round(float(bbox.ZMax), 4),
            "x_len": round(float(bbox.XLength), 4),
            "y_len": round(float(bbox.YLength), 4),
            "z_len": round(float(bbox.ZLength), 4),
            "center": center,
        }

    return {
        "vertices": vertices,
        "indices": indices,
        "edges": edges_list,
        "faces_map": faces_map,
        "edges_map": edges_map,
        "bounds": bounds,
        "stats": {
            "vertex_count": len(shape.Vertexes),
            "facet_count": len(facets),
            "edge_segments": len(edges_list),
            "edge_count": len(shape.Edges),
            "face_count": len(shape.Faces),
            "solid_count": len(shape.Solids),
        },
    }


def extract_brep_mesh(
    step_file: str | Path,
    tolerance: float = 0.2,
) -> Dict[str, Any]:
    """Extract 3D triangulated mesh, sharp boundary edges, and complete B-Rep topology from a STEP file."""
    load_res = load_step(step_file)
    shape = load_res.primary_shape
    if not shape:
        load_res.close()
        raise ValueError("No primary solid shape found in STEP file.")
    try:
        return extract_mesh_from_shape(shape, tolerance=tolerance)
    finally:
        load_res.close()


def export_mesh_from_shape(shape: Part.Shape, output_file: str | Path, tolerance: float = 0.2) -> Path:
    """Extract and write mesh JSON to disk directly from loaded shape."""
    data = extract_mesh_from_shape(shape, tolerance=tolerance)
    out_path = Path(output_file).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data), encoding="utf-8")
    return out_path


def export_mesh_json(step_file: str | Path, output_file: str | Path) -> Path:
    """Extract and write mesh JSON to disk."""
    data = extract_brep_mesh(step_file)
    out_path = Path(output_file).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    import sys
    step = sys.argv[1] if len(sys.argv) > 1 else "input/Pieza18_1.STEP"
    out = sys.argv[2] if len(sys.argv) > 2 else "output/Pieza18_1_mesh.json"
    res = export_mesh_json(step, out)
    print(f"Exported 3D B-Rep mesh to: {res}")
