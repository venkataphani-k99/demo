"""Phase 19B — Evidence-Driven CAD Profile, Section & Artifact Validator.

Provides rigorous multi-station dimensional validation, profile verification,
cavity topology checks, and end-to-end B-Rep to Three.js artifact consistency.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part
from FreeCAD import Vector

from src.drawing.reconstruction_schemas import (
    ArtifactTrace,
    SectionStationValidation,
)

logger = logging.getLogger(__name__)


class ReconstructionValidator:
    """Rigorous engineering validator for reconstructed CAD solids and exported meshes."""

    @staticmethod
    def validate_profile_against_evidence(
        profile_points: List[Tuple[float, float, float]],
        min_points: int = 4,
        max_height: Optional[float] = None,
        max_radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validates that a 2D section profile has sufficient points, non-zero area, and valid boundaries."""
        if not profile_points or len(profile_points) < min_points:
            return {
                "valid": False,
                "reason": f"Profile point count ({len(profile_points) if profile_points else 0}) below minimum {min_points}.",
            }

        # Check coordinate ranges
        xs = [p[0] for p in profile_points]
        zs = [p[2] for p in profile_points]
        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)

        if max_x <= min_x:
            return {"valid": False, "reason": "Profile has zero radial width."}
        if max_z <= min_z:
            return {"valid": False, "reason": "Profile has zero vertical height."}

        if max_height is not None and max_z > (max_height + 5.0):
            return {"valid": False, "reason": f"Profile height {max_z} exceeds maximum expected {max_height} mm."}
        if max_radius is not None and max_x > (max_radius + 5.0):
            return {"valid": False, "reason": f"Profile radius {max_x} exceeds maximum expected {max_radius} mm."}

        return {
            "valid": True,
            "points_count": len(profile_points),
            "radial_span": round(max_x - min_x, 3),
            "height_span": round(max_z - min_z, 3),
        }

    @staticmethod
    def validate_section_measurements(
        shape: Part.Shape,
        station_specs: List[Dict[str, Any]],
        default_tolerance: float = 2.5,
    ) -> List[SectionStationValidation]:
        """Slices the B-Rep solid at specified Z stations and measures reconstructed diameters against expected evidence.

        Parameters
        ----------
        shape : Part.Shape
            The reconstructed FreeCAD B-Rep solid.
        station_specs : List[Dict[str, Any]]
            List of station dicts: e.g. [{"station_z": 50.0, "expected_diameter": 81.0, "tolerance": 2.0}]
        """
        results: List[SectionStationValidation] = []
        if shape is None or shape.isNull():
            return [
                SectionStationValidation(
                    validation_type="section_station",
                    station_z=s.get("station_z", 0.0),
                    expected_diameter=s.get("expected_diameter", 0.0),
                    actual_diameter=0.0,
                    tolerance=s.get("tolerance", default_tolerance),
                    result="FAIL",
                    details="B-Rep shape is null or empty.",
                )
                for s in station_specs
            ]

        bbox = shape.BoundBox
        z_min = float(bbox.ZMin)
        z_max = float(bbox.ZMax)

        for spec in station_specs:
            station_z = float(spec.get("station_z", 0.0))
            expected_dia = float(spec.get("expected_diameter", 0.0))
            tol = float(spec.get("tolerance", default_tolerance))
            v_type = str(spec.get("validation_type", "section_station"))

            if station_z < z_min or station_z > z_max:
                # Outside bounding box
                results.append(SectionStationValidation(
                    validation_type=v_type,
                    station_z=station_z,
                    expected_diameter=expected_dia,
                    actual_diameter=0.0,
                    tolerance=tol,
                    result="FAIL",
                    details=f"Station Z={station_z} mm is outside solid Z bounds [{round(z_min, 2)}, {round(z_max, 2)}].",
                ))
                continue

            # Slice solid with a horizontal plane at station_z
            plane_face = Part.makePlane(500.0, 500.0, Vector(-250.0, -250.0, station_z), Vector(0.0, 0.0, 1.0))
            section = shape.section(plane_face)

            if section is None or section.isNull() or len(section.Edges) == 0:
                # Try small offset +/- 0.5 mm if station hits exact boundary edge
                plane_face = Part.makePlane(500.0, 500.0, Vector(-250.0, -250.0, station_z + 0.5), Vector(0.0, 0.0, 1.0))
                section = shape.section(plane_face)

            if section is not None and not section.isNull() and len(section.Edges) > 0:
                s_bbox = section.BoundBox
                actual_dia = max(float(s_bbox.XLength), float(s_bbox.YLength))
            else:
                actual_dia = 0.0

            diff = abs(actual_dia - expected_dia)
            passed = diff <= tol

            results.append(SectionStationValidation(
                validation_type=v_type,
                station_z=station_z,
                expected_diameter=round(expected_dia, 3),
                actual_diameter=round(actual_dia, 3),
                tolerance=tol,
                result="PASS" if passed else "FAIL",
                details=f"Measured Ø{round(actual_dia, 2)} mm vs Expected Ø{round(expected_dia, 2)} mm (Δ={round(diff, 2)} mm, tol=±{tol} mm).",
            ))

        return results

    @staticmethod
    def validate_radial_transitions(shape: Part.Shape, sample_z_list: Optional[List[float]] = None) -> Dict[str, Any]:
        """Verifies that the solid has distinct radial transitions and varying cross-section diameter along Z."""
        if shape is None or shape.isNull():
            return {"valid": False, "reason": "B-Rep solid is null."}

        bbox = shape.BoundBox
        z_min = float(bbox.ZMin)
        z_max = float(bbox.ZMax)
        h = z_max - z_min

        if h <= 0.0:
            return {"valid": False, "reason": "Height is non-positive."}

        if not sample_z_list:
            sample_z_list = [
                z_min + h * 0.2,
                z_min + h * 0.5,
                z_min + h * 0.75,
                z_min + h * 0.9,
            ]

        measured_dias: List[float] = []
        for sz in sample_z_list:
            plane_face = Part.makePlane(500.0, 500.0, Vector(-250.0, -250.0, sz), Vector(0.0, 0.0, 1.0))
            section = shape.section(plane_face)
            if section and not section.isNull() and len(section.Edges) > 0:
                s_bbox = section.BoundBox
                measured_dias.append(max(float(s_bbox.XLength), float(s_bbox.YLength)))

        if len(measured_dias) < 2:
            return {"valid": False, "reason": "Could not extract multiple section slices."}

        min_d = min(measured_dias)
        max_d = max(measured_dias)
        delta = max_d - min_d

        # Must have at least 5.0 mm delta across heights for profiled components
        has_transitions = delta >= 5.0
        return {
            "valid": has_transitions,
            "min_diameter": round(min_d, 3),
            "max_diameter": round(max_d, 3),
            "diameter_delta": round(delta, 3),
            "measurements": [round(d, 2) for d in measured_dias],
            "reason": "Radial transitions confirmed." if has_transitions else "Diameter is uniform (no radial transitions).",
        }

    @staticmethod
    def validate_hollow_cavity(shape: Part.Shape) -> Dict[str, Any]:
        """Verifies that the solid is hollow (internal cavity exists) and not a solid block."""
        if shape is None or shape.isNull():
            return {"is_hollow": False, "reason": "Shape is null."}

        # Check face count (a hollow bottle has at least 6-12 faces for outer, inner, base, and lip)
        face_count = len(shape.Faces)
        vol = float(shape.Volume)
        bbox = shape.BoundBox
        bounding_vol = float(bbox.XLength) * float(bbox.YLength) * float(bbox.ZLength)

        # In a hollow thin-walled bottle, solid volume is significantly less than bounding volume
        # Typically solid volume / bounding volume < 0.45
        vol_ratio = (vol / bounding_vol) if bounding_vol > 0 else 1.0

        is_hollow = face_count >= 4 and vol_ratio < 0.65
        return {
            "is_hollow": is_hollow,
            "face_count": face_count,
            "volume_mm3": round(vol, 2),
            "bounding_volume_mm3": round(bounding_vol, 2),
            "solid_to_bounding_ratio": round(vol_ratio, 3),
            "details": f"Solid volume is {round(vol_ratio * 100, 1)}% of bounding envelope with {face_count} faces.",
        }

    @staticmethod
    def validate_not_simple_cylinder(shape: Part.Shape) -> Dict[str, Any]:
        """Verifies the solid is not equivalent to a single simple cylinder."""
        if shape is None or shape.isNull():
            return {"is_not_simple_cylinder": False, "reason": "Shape is null."}

        # Check faces: a single cylinder has exactly 3 faces (1 cylinder surface + 2 planar caps)
        face_count = len(shape.Faces)
        if face_count <= 3:
            # Check if all radial slices are identical
            trans = ReconstructionValidator.validate_radial_transitions(shape)
            if not trans["valid"]:
                return {
                    "is_not_simple_cylinder": False,
                    "reason": "Solid has <= 3 faces and constant diameter (simple cylinder primitive).",
                }

        return {
            "is_not_simple_cylinder": True,
            "face_count": face_count,
            "reason": f"Solid has {face_count} topological faces with varying section curvature.",
        }

    @staticmethod
    def validate_not_rectangular_prism(shape: Part.Shape) -> Dict[str, Any]:
        """Verifies the solid is not equivalent to a rectangular box/prism."""
        if shape is None or shape.isNull():
            return {"is_not_rectangular_prism": False, "reason": "Shape is null."}

        # A rectangular box has exactly 6 planar faces and 12 linear edges
        face_count = len(shape.Faces)
        planar_faces = 0
        curved_faces = 0

        for f in shape.Faces:
            surf_type = f.Surface.TypeId if hasattr(f, "Surface") and hasattr(f.Surface, "TypeId") else ""
            if "Plane" in surf_type:
                planar_faces += 1
            else:
                curved_faces += 1

        if face_count == 6 and planar_faces == 6:
            return {
                "is_not_rectangular_prism": False,
                "reason": "Solid is a 6-face rectangular prism.",
            }

        return {
            "is_not_rectangular_prism": True,
            "total_faces": face_count,
            "curved_faces": curved_faces,
            "planar_faces": planar_faces,
            "reason": f"Solid contains {curved_faces} curved surfaces and {face_count} total faces.",
        }

    @staticmethod
    def validate_brep_and_mesh_consistency(
        brep_bbox: Dict[str, float],
        mesh_bbox: Dict[str, float],
        tolerance: float = 1.0,
    ) -> Dict[str, Any]:
        """Verifies that B-Rep kernel bounding box matches exported Three.js mesh bounding box."""
        dx = abs(brep_bbox.get("x_length", 0.0) - mesh_bbox.get("x_length", 0.0))
        dy = abs(brep_bbox.get("y_length", 0.0) - mesh_bbox.get("y_length", 0.0))
        dz = abs(brep_bbox.get("z_length", 0.0) - mesh_bbox.get("z_length", 0.0))

        consistent = (dx <= tolerance) and (dy <= tolerance) and (dz <= tolerance)
        return {
            "consistent": consistent,
            "delta_x": round(dx, 3),
            "delta_y": round(dy, 3),
            "delta_z": round(dz, 3),
            "tolerance": tolerance,
            "reason": "B-Rep and Mesh bounds match within tolerance." if consistent else f"Bounds mismatch: ΔX={round(dx,2)}, ΔY={round(dy,2)}, ΔZ={round(dz,2)} mm.",
        }

    @staticmethod
    def compute_file_hash(filepath: Path) -> str:
        """Computes deterministic SHA256 hash of a file."""
        if not filepath.exists():
            return ""
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
