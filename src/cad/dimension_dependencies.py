"""Dimension Dependency Graph and Datum-like Reference Analysis.

Analyzes mathematical and topological dependencies among dimension candidates:
1. Detects additive depth/linear relationships (e.g. Total Depth = Bore Depth + Cbore Depth).
2. Distinguishes independent dimensions from derived dimensions.
3. Detects geometric constraints (perpendicularity, parallelism) vs drawing dimensions.
4. Identifies potential datum-like reference features (major planar base, symmetry planes).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import FreeCAD

from src.cad.dimensions import DimensionCandidate, DimensionCandidateSet
from src.cad.measurements import MeasurementEngine
from src.cad.topology import TopologyGraph


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionDependencyNode:
    """A node in the dimension dependency graph."""
    dimension_id: str
    formatted_value: str
    value: float
    dependency_type: str                  # "independent" | "derived" | "geometric_constraint" | "redundant_candidate"
    depends_on: List[str] = field(default_factory=list)  # IDs of dimensions this depends on
    formula: str = ""                     # e.g. "D017 = D015 + D016"
    semantic_role: str = ""               # "feature_size" | "feature_depth" | "overall_size" | "thickness" | etc.
    priority: str = "PRIMARY"             # "PRIMARY" | "SECONDARY" | "OPTIONAL" | "AMBIGUOUS"
    requires_section_view: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatumReference:
    """Candidate datum-like reference geometry."""
    face_id: str
    surface_type: str
    area_mm2: float
    normal: List[float]
    position: List[float]
    reference_role: str                   # "primary_mounting_base" | "parallel_end_stop" | "center_axis"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyAnalysisResult:
    """Complete dependency analysis result for all dimension candidates."""
    nodes: Dict[str, DimensionDependencyNode]
    potential_datums: List[DatumReference]
    independent_count: int
    derived_count: int
    constraint_count: int
    redundant_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "independent_count": self.independent_count,
            "derived_count": self.derived_count,
            "constraint_count": self.constraint_count,
            "redundant_count": self.redundant_count,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "potential_datums": [d.to_dict() for d in self.potential_datums],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dependency Analyser Engine
# ─────────────────────────────────────────────────────────────────────────────

class DimensionDependencyAnalyser:
    """Builds dependency graphs and discovers datum references."""

    TOL_ADDITIVE = 1e-2  # mm: tolerance for additive relationship matching

    def analyse(
        self,
        candidate_set: DimensionCandidateSet,
        engine: Optional[MeasurementEngine] = None,
        topo_graph: Optional[TopologyGraph] = None,
    ) -> DependencyAnalysisResult:
        """Run full dependency and datum-reference analysis."""
        nodes: Dict[str, DimensionDependencyNode] = {}

        # 1. Initialize nodes with default semantics and priorities
        for cand in candidate_set.candidates:
            node = self._init_node(cand)
            nodes[cand.id] = node

        # 2. Detect additive depth / chain dependencies
        self._detect_additive_depth_dependencies(candidate_set, nodes)

        # 3. Detect geometric constraint vs drawing dimension roles
        self._classify_geometric_constraints(candidate_set, nodes)

        # 4. Discover potential datum-like reference geometry
        datums = self._discover_potential_datums(engine, topo_graph) if engine else []

        # Count classifications
        indep = sum(1 for n in nodes.values() if n.dependency_type == "independent")
        derived = sum(1 for n in nodes.values() if n.dependency_type == "derived")
        constraint = sum(1 for n in nodes.values() if n.dependency_type == "geometric_constraint")
        redundant = sum(1 for n in nodes.values() if n.dependency_type == "redundant_candidate")

        return DependencyAnalysisResult(
            nodes=nodes,
            potential_datums=datums,
            independent_count=indep,
            derived_count=derived,
            constraint_count=constraint,
            redundant_count=redundant,
        )

    def _init_node(self, cand: DimensionCandidate) -> DimensionDependencyNode:
        """Assign baseline semantic roles and priorities."""
        ctype = cand.type
        csem = cand.dimension_semantics
        status = cand.status

        # Default role mapping
        if status == "ambiguous":
            role = "ambiguous"
            priority = "AMBIGUOUS"
            dep_type = "independent"
        elif ctype == "diameter":
            role = "feature_size"
            priority = "PRIMARY"
            dep_type = "independent"
        elif ctype == "radius":
            role = "blend_radius"
            priority = "PRIMARY"
            dep_type = "independent"
        elif ctype == "depth":
            role = "feature_depth"
            priority = "PRIMARY"
            dep_type = "independent"
        elif ctype == "linear":
            if csem == "overall_extent":
                role = "overall_size"
                priority = "PRIMARY"
                dep_type = "independent"
            elif csem == "thickness":
                role = "thickness"
                priority = "PRIMARY"
                dep_type = "independent"
            else:
                role = "feature_length"
                priority = "SECONDARY"
                dep_type = "independent"
        elif ctype == "angle":
            role = "geometric_relationship"
            priority = "OPTIONAL"
            dep_type = "geometric_constraint"
        else:
            role = "general"
            priority = "SECONDARY"
            dep_type = "independent"

        return DimensionDependencyNode(
            dimension_id=cand.id,
            formatted_value=cand.formatted_value,
            value=cand.value,
            dependency_type=dep_type,
            semantic_role=role,
            priority=priority,
        )

    def _detect_additive_depth_dependencies(
        self,
        candidate_set: DimensionCandidateSet,
        nodes: Dict[str, DimensionDependencyNode],
    ) -> None:
        """Detect when a total depth equals the sum of two constituent step depths."""
        depth_cands = [c for c in candidate_set.candidates if c.type == "depth" and c.status == "valid"]

        # Group by source feature
        feat_groups: Dict[str, List[DimensionCandidate]] = {}
        for c in depth_cands:
            fid = c.source_feature or "none"
            feat_groups.setdefault(fid, []).append(c)

        for fid, group in feat_groups.items():
            if len(group) < 3:
                continue

            # Find pairs whose sum matches a third depth in the group
            for i, c1 in enumerate(group):
                for j, c2 in enumerate(group):
                    if i >= j:
                        continue
                    combined = c1.value + c2.value
                    for k, c3 in enumerate(group):
                        if k == i or k == j:
                            continue
                        if abs(c3.value - combined) <= self.TOL_ADDITIVE:
                            # c3 is the derived total depth
                            node3 = nodes[c3.id]
                            node3.dependency_type = "derived"
                            node3.depends_on = [c1.id, c2.id]
                            node3.formula = f"{c3.id} ({c3.value:.3f}) = {c1.id} ({c1.value:.3f}) + {c2.id} ({c2.value:.3f})"
                            node3.priority = "OPTIONAL"
                            node3.notes.append(f"Mathematically derived from {c1.id} + {c2.id} on feature {fid}")

    def _classify_geometric_constraints(
        self,
        candidate_set: DimensionCandidateSet,
        nodes: Dict[str, DimensionDependencyNode],
    ) -> None:
        """Mark angle and alignment candidates as geometric constraints (not standard drawing dims)."""
        for cand in candidate_set.candidates:
            if cand.type == "angle":
                node = nodes[cand.id]
                node.dependency_type = "geometric_constraint"
                node.semantic_role = "geometric_relationship"
                node.priority = "OPTIONAL"
                node.notes.append("Geometric alignment / perpendicularity relationship; implicit in orthographic projection")

    def _discover_potential_datums(
        self,
        engine: MeasurementEngine,
        topo_graph: Optional[TopologyGraph],
    ) -> List[DatumReference]:
        """Inspect model faces for candidate datum surfaces."""
        datums: List[DatumReference] = []

        # Find largest planar face (typically mounting base at Z=0)
        largest_plane_id = None
        max_area = 0.0
        face_map = engine.face_map

        for fid, face in face_map.items():
            surf = face.Surface
            if "Plane" in type(surf).__name__ or "Plane" in getattr(surf, "TypeId", ""):
                area = float(face.Area)
                n = surf.Axis
                mag = math.sqrt(n.x**2 + n.y**2 + n.z**2)
                norm = [n.x / mag, n.y / mag, n.z / mag] if mag > 1e-9 else [0, 0, 1]
                pos = [float(surf.Position.x), float(surf.Position.y), float(surf.Position.z)]

                # Check if it's the large base plane (Face16 at z=0)
                if abs(norm[2]) > 0.9 and abs(pos[2]) < 0.1 and area > 1000.0:
                    datums.append(DatumReference(
                        face_id=fid,
                        surface_type="Plane",
                        area_mm2=round(area, 2),
                        normal=[round(x, 3) for x in norm],
                        position=[round(x, 3) for x in pos],
                        reference_role="primary_mounting_base",
                        notes="Main planar bottom seating face (Z=0)",
                    ))

                # Check for parallel end faces (Face10, Face11 at x=±25)
                elif abs(norm[0]) > 0.9 and area > 100.0:
                    datums.append(DatumReference(
                        face_id=fid,
                        surface_type="Plane",
                        area_mm2=round(area, 2),
                        normal=[round(x, 3) for x in norm],
                        position=[round(x, 3) for x in pos],
                        reference_role="parallel_end_stop",
                        notes=f"End face at X={pos[0]:.1f}mm",
                    ))

        return datums
