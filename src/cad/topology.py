"""Topology graph extractor for CAD B-Rep shapes.

Builds bidirectional topological relationships between Faces, Edges, and Vertices:
- Face -> Boundary Edges
- Edge -> Shared Faces
- Face -> Adjacent Faces (dual graph)
- Face -> Outer and Inner Wires
- Edge -> Vertices
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

import FreeCAD
import Part


@dataclass
class FaceTopology:
    face_id: str
    face_index: int  # 1-indexed
    edge_ids: List[str] = field(default_factory=list)
    adjacent_face_ids: List[str] = field(default_factory=list)
    outer_edge_ids: List[str] = field(default_factory=list)
    inner_wire_edge_ids: List[List[str]] = field(default_factory=list)
    wire_count: int = 1


@dataclass
class EdgeTopology:
    edge_id: str
    edge_index: int  # 1-indexed
    face_ids: List[str] = field(default_factory=list)
    vertex_ids: List[str] = field(default_factory=list)
    is_seam: bool = False
    is_boundary: bool = False  # shared by only 1 face (open shell)
    is_manifold: bool = True   # shared by exactly 2 faces


@dataclass
class TopologyGraph:
    faces: Dict[str, FaceTopology]
    edges: Dict[str, EdgeTopology]
    edge_to_faces: Dict[str, List[str]]
    face_to_edges: Dict[str, List[str]]
    face_adjacency: Dict[str, List[str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_to_faces": self.edge_to_faces,
            "face_to_edges": self.face_to_edges,
            "face_adjacency": self.face_adjacency,
        }


def build_topology_graph(shape: Part.Shape) -> TopologyGraph:
    """Extract complete bidirectional topology relationship graph from B-Rep shape.

    Args:
        shape: FreeCAD Part::TopoShape object.

    Returns:
        TopologyGraph with mapped face-edge-face relationships.
    """
    if shape is None or shape.isNull():
        raise ValueError("Cannot build topology graph from null shape.")

    faces_list = shape.Faces
    edges_list = shape.Edges
    vertices_list = shape.Vertexes

    # Pre-index global edges and vertices
    # Note: shape.Edges and shape.Vertexes provide canonical 0-indexed order
    face_topos: Dict[str, FaceTopology] = {}
    edge_topos: Dict[str, EdgeTopology] = {}

    edge_to_faces: Dict[str, List[str]] = {}
    face_to_edges: Dict[str, List[str]] = {}
    face_adjacency_set: Dict[str, Set[str]] = {}

    # Initialize edge topologies
    for e_idx, e in enumerate(edges_list):
        e_id = f"Edge{e_idx + 1}"
        
        # Map vertices
        v_ids = []
        for ev in e.Vertexes:
            for v_idx, gv in enumerate(vertices_list):
                if ev.isSame(gv):
                    v_ids.append(f"Vertex{v_idx + 1}")
                    break

        edge_topos[e_id] = EdgeTopology(
            edge_id=e_id,
            edge_index=e_idx + 1,
            face_ids=[],
            vertex_ids=v_ids,
        )
        edge_to_faces[e_id] = []

    # Map Faces -> Edges and populate edge_to_faces
    for f_idx, f in enumerate(faces_list):
        f_id = f"Face{f_idx + 1}"
        face_edges: List[str] = []
        face_adjacency_set[f_id] = set()

        # Map all edges of the face
        for fe in f.Edges:
            for e_idx, ge in enumerate(edges_list):
                if fe.isSame(ge):
                    e_id = f"Edge{e_idx + 1}"
                    face_edges.append(e_id)
                    if f_id not in edge_to_faces[e_id]:
                        edge_to_faces[e_id].append(f_id)
                        edge_topos[e_id].face_ids.append(f_id)
                    break

        face_to_edges[f_id] = face_edges

        # Distinguish outer wire edges vs inner wire edges (hole loops)
        outer_edges: List[str] = []
        if hasattr(f, "OuterWire") and f.OuterWire:
            for oe in f.OuterWire.Edges:
                for e_idx, ge in enumerate(edges_list):
                    if oe.isSame(ge):
                        outer_edges.append(f"Edge{e_idx + 1}")
                        break

        inner_wires: List[List[str]] = []
        if hasattr(f, "Wires") and len(f.Wires) > 1:
            for wire in f.Wires:
                if hasattr(f, "OuterWire") and f.OuterWire and wire.isSame(f.OuterWire):
                    continue
                wire_edge_ids = []
                for we in wire.Edges:
                    for e_idx, ge in enumerate(edges_list):
                        if we.isSame(ge):
                            wire_edge_ids.append(f"Edge{e_idx + 1}")
                            break
                if wire_edge_ids:
                    inner_wires.append(wire_edge_ids)

        face_topos[f_id] = FaceTopology(
            face_id=f_id,
            face_index=f_idx + 1,
            edge_ids=face_edges,
            adjacent_face_ids=[],  # populated next
            outer_edge_ids=outer_edges,
            inner_wire_edge_ids=inner_wires,
            wire_count=len(f.Wires),
        )

    # Derive Face Adjacency from shared edges
    for e_id, f_ids in edge_to_faces.items():
        e_topo = edge_topos[e_id]
        if len(f_ids) == 1:
            e_topo.is_boundary = True
            e_topo.is_manifold = False
        elif len(f_ids) == 2:
            e_topo.is_manifold = True
        else:
            e_topo.is_manifold = False

        for f1 in f_ids:
            for f2 in f_ids:
                if f1 != f2:
                    face_adjacency_set[f1].add(f2)

    # Finalize sorted adjacency lists
    face_adjacency: Dict[str, List[str]] = {}
    for f_id, adj_set in face_adjacency_set.items():
        sorted_adj = sorted(
            list(adj_set),
            key=lambda x: int(x.replace("Face", "")) if x.replace("Face", "").isdigit() else x,
        )
        face_adjacency[f_id] = sorted_adj
        face_topos[f_id].adjacent_face_ids = sorted_adj

    return TopologyGraph(
        faces=face_topos,
        edges=edge_topos,
        edge_to_faces=edge_to_faces,
        face_to_edges=face_to_edges,
        face_adjacency=face_adjacency,
    )
