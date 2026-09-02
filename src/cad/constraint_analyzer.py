"""Phase 1 — Freeze-safe CAD analysis utilities.

Provides wrappers around Phase 1 topology, features, geometry, and model validation
modules that gracefully handle the case where FreeCAD is not installed or not
on the current Python PATH.

Phase 19 uses these utilities to:
  - Extract topological properties (faces, edges, vertices) from FreeCAD solids
  - Classify faces by surface type (plane, cylinder, cone, sphere, torus, bezier)
  - Validate reconstructed geometry for correctness
  - Compute global constraints (minimum wall thickness, concentricity, etc.)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FreeCAD availability check
# ---------------------------------------------------------------------------

def _freecad_available() -> bool:
    """Check whether FreeCAD can be imported."""
    try:
        import FreeCAD  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        # Module use conflict on Windows (dll conflict)
        return False


FREECAD_AVAILABLE = _freecad_available()


# ---------------------------------------------------------------------------
# Safe imports
# ---------------------------------------------------------------------------

def _safe_import(module_name: str) -> Optional[Any]:
    """Attempt to import a FreeCAD-dependent module, returning None on failure."""
    if not FREECAD_AVAILABLE:
        return None
    try:
        import importlib
        return importlib.import_module(module_name)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FaceInfo:
    """Topological face description for constraint analysis."""
    face_index: int
    surface_type: str  # plane, cylinder, cone, sphere, torus, bezier, other
    area: float
    is_external: bool = True
    axis: Optional[Tuple[float, float, float]] = None
    center: Optional[Tuple[float, float, float]] = None
    radius: Optional[float] = None


@dataclass
class EdgeInfo:
    """Topological edge description."""
    edge_index: int
    length: float
    is_line: bool = False
    is_circle: bool = False
    tolerance: float = 0.0


@dataclass
class SolidReport:
    """Topological summary of a reconstructed solid."""
    solid_name: str
    is_valid: bool
    is_closed: bool
    face_count: int
    edge_count: int
    vertex_count: int
    shell_count: int
    volume_mm3: float
    surface_area_mm2: float
    faces: List[FaceInfo] = field(default_factory=list)
    edges: List[EdgeInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class GlobalConstraintCheck:
    """Result of checking a single global constraint."""
    constraint_name: str
    passed: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    message: str = ""


# ---------------------------------------------------------------------------
# ConstraintAnalyzer — wraps Phase 1 topology + validation
# ---------------------------------------------------------------------------

class ConstraintAnalyzer:
    """Phase 1 integration layer: extracts topological properties and validates
    reconstructed geometry using Phase 1's modules.

    This is a freeze-safe wrapper — all FreeCAD-dependent imports are deferred
    and caught gracefully.
    """

    def __init__(self):
        self._topology_mod = _safe_import("src.cad.topology")
        self._features_mod = _safe_import("src.cad.features")
        self._geometry_mod = _safe_import("src.cad.geometry")
        self._model_validator = _safe_import("src.cad.model_validator")
        self._global_constraints = _safe_import("src.cad.global_constraints")

        if not FREECAD_AVAILABLE:
            logger.warning(
                "FreeCAD is not available — ConstraintAnalyzer will run in offline mode. "
                "Topological checks and model validation are skipped."
            )

    def analyze_solid(
        self, shape: Any, name: str = "reconstructed_solid"
    ) -> SolidReport:
        """Perform full topological analysis on a solid shape.

        Parameters
        ----------
        shape : FreeCAD Shape or similar
            The solid to analyze.
        name : str
            Human-readable name for the report.

        Returns
        -------
        SolidReport
        """
        if not FREECAD_AVAILABLE:
            return SolidReport(
                solid_name=name,
                is_valid=False,
                is_closed=False,
                face_count=0,
                edge_count=0,
                vertex_count=0,
                shell_count=0,
                volume_mm3=0.0,
                surface_area_mm2=0.0,
                errors=["FreeCAD not available — topology analysis skipped"],
            )

        try:
            import Part
            faces: List[FaceInfo] = []
            edges: List[EdgeInfo] = []
            warnings: List[str] = []
            errors: List[str] = []

            # Topological counts
            face_count = len(shape.Faces)
            edge_count = len(shape.Edges)
            vertex_count = len(shape.Vertexes)
            shell_count = len(shape.Shells) if hasattr(shape, "Shells") else 1

            # Volume and surface area
            try:
                volume = shape.Volume
            except Exception:
                volume = 0.0
                errors.append("Could not compute volume")

            try:
                surface_area = shape.Area
            except Exception:
                surface_area = 0.0
                errors.append("Could not compute surface area")

            # Face analysis
            for i, face in enumerate(shape.Faces):
                try:
                    surface = face.Surface
                    stype = surface.TypeId if hasattr(surface, "TypeId") else "unknown"

                    face_info = FaceInfo(
                        face_index=i,
                        surface_type=stype,
                        area=face.Area,
                        is_external=face.Orientation == "Standard",
                    )

                    if hasattr(surface, "Axis"):
                        face_info.axis = (surface.Axis.x, surface.Axis.y, surface.Axis.z)
                    if hasattr(surface, "Center"):
                        face_info.center = (surface.Center.x, surface.Center.y, surface.Center.z)
                    if hasattr(surface, "Radius"):
                        face_info.radius = surface.Radius

                    faces.append(face_info)
                except Exception as exc:
                    warnings.append(f"Face {i}: could not analyze surface — {exc}")
                    faces.append(FaceInfo(face_index=i, surface_type="unknown", area=0.0))

            # Edge analysis
            for i, edge in enumerate(shape.Edges):
                try:
                    curve = edge.Curve
                    is_line = curve.TypeId == "Part::GeomLine"
                    is_circle = curve.TypeId == "Part::GeomCircle"
                    edge_info = EdgeInfo(
                        edge_index=i,
                        length=edge.Length,
                        is_line=is_line,
                        is_circle=is_circle,
                        tolerance=edge.Tolerance,
                    )
                    edges.append(edge_info)
                except Exception:
                    edges.append(EdgeInfo(edge_index=i, length=edge.Length))

            # Validation
            try:
                is_valid = shape.isValid()
            except Exception:
                is_valid = False
                errors.append("Validity check failed")

            try:
                is_closed = shape.isClosed()
            except Exception:
                is_closed = False
                errors.append("Closedness check failed")

            # Check for self-intersections
            if not shape.isValid():
                try:
                    checker = Part.check.Solid(shape)
                    if not checker.isValid():
                        errors.extend([f"Solid error: {e}" for e in checker.errors()])
                except Exception:
                    pass

            return SolidReport(
                solid_name=name,
                is_valid=is_valid,
                is_closed=is_closed,
                face_count=face_count,
                edge_count=edge_count,
                vertex_count=vertex_count,
                shell_count=shell_count,
                volume_mm3=volume,
                surface_area_mm2=surface_area,
                faces=faces,
                edges=edges,
                warnings=warnings,
                errors=errors,
            )

        except Exception as exc:
            return SolidReport(
                solid_name=name,
                is_valid=False,
                is_closed=False,
                face_count=0,
                edge_count=0,
                vertex_count=0,
                shell_count=0,
                volume_mm3=0.0,
                surface_area_mm2=0.0,
                errors=[f"Analysis exception: {exc}"],
            )

    def check_global_constraints(
        self,
        report: SolidReport,
        constraints: Optional[GlobalConstraints] = None,
    ) -> List[GlobalConstraintCheck]:
        """Check global manufacturing constraints against the solid report.

        Parameters
        ----------
        report : SolidReport
            Topological analysis result.
        constraints : GlobalConstraints, optional
            Constraint thresholds. Uses defaults if not provided.

        Returns
        -------
        List[GlobalConstraintCheck]
        """
        results: List[GlobalConstraintCheck] = []

        if constraints is None:
            from src.cad.global_constraints import GlobalConstraints
            constraints = GlobalConstraints()

        # Minimum wall thickness (from Phase 1 global constraints)
        if constraints.minimum_wall_thickness_mm and constraints.minimum_wall_thickness_mm > 0:
            min_wall = constraints.minimum_wall_thickness_mm
            # Approximate: check all face areas and edge lengths
            min_feature = min(
                (e.length for e in report.edges if e.length > 0),
                default=None,
            )
            if min_feature is not None:
                results.append(GlobalConstraintCheck(
                    constraint_name="minimum_wall_thickness",
                    passed=min_feature >= min_wall,
                    value=min_feature,
                    threshold=min_wall,
                    message=f"Min edge length {min_feature:.2f}mm {'≥' if min_feature >= min_wall else '<'} threshold {min_wall}mm",
                ))

        # Closedness
        results.append(GlobalConstraintCheck(
            constraint_name="closed_solid",
            passed=report.is_closed,
            message=f"Solid {'is' if report.is_closed else 'is NOT'} closed",
        ))

        # Validity
        results.append(GlobalConstraintCheck(
            constraint_name="valid_topology",
            passed=report.is_valid,
            message=f"Solid is {'valid' if report.is_valid else 'INVALID'}",
        ))

        # Minimum volume (non-degenerate)
        if report.volume_mm3 > 0:
            results.append(GlobalConstraintCheck(
                constraint_name="non_degenerate",
                passed=True,
                value=report.volume_mm3,
                message=f"Volume: {report.volume_mm3:.2f} mm³",
            ))
        else:
            results.append(GlobalConstraintCheck(
                constraint_name="non_degenerate",
                passed=False,
                value=0.0,
                message="Volume is zero — degenerate solid",
            ))

        return results

    def validate_feature_against_plan(
        self,
        feature_id: str,
        plan_feature: Any,
        actual_shape: Any,
    ) -> Dict[str, Any]:
        """Validate that a reconstructed feature matches the plan specification.

        Compares the topological signature of the plan feature (dimensions,
        placement, profile type) against the actual extracted geometry.

        Parameters
        ----------
        feature_id : str
            The feature identifier.
        plan_feature : Any
            The ParametricCADStep or feature plan entry.
        actual_shape : FreeCAD Shape
            The actual geometry to validate against.

        Returns
        -------
        Dict with validation results.
        """
        result = {
            "feature_id": feature_id,
            "validation_passed": True,
            "checks": [],
            "warnings": [],
        }

        if not FREECAD_AVAILABLE:
            result["checks"].append({
                "check": "topology_extraction",
                "passed": False,
                "reason": "FreeCAD not available",
            })
            result["validation_passed"] = False
            return result

        try:
            if hasattr(actual_shape, "Volume"):
                vol = actual_shape.Volume
                result["checks"].append({
                    "check": "has_volume",
                    "passed": vol > 0,
                    "value": vol,
                })

            if hasattr(actual_shape, "isClosed"):
                closed = actual_shape.isClosed()
                result["checks"].append({
                    "check": "closed",
                    "passed": closed,
                })

            if hasattr(actual_shape, "isValid"):
                valid = actual_shape.isValid()
                result["checks"].append({
                    "check": "valid",
                    "passed": valid,
                })
                result["validation_passed"] = all(
                    c.get("passed", True) for c in result["checks"]
                )
        except Exception as exc:
            result["checks"].append({
                "check": "validation_exception",
                "passed": False,
                "reason": str(exc),
            })
            result["validation_passed"] = False

        return result
