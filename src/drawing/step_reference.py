"""Phase 19C — STEP Reference Bridge for 2D Drawing Reconstruction.

Extracts authoritative geometry from the original STEP file to supplement
drawing evidence. Uses cylindrical FACE analysis for reliable classification.

The STEP file is used ONLY as a dimension/position reference — all geometry
is rebuilt from scratch in FreeCAD.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class HoleReference:
    """Reference data for a hole from the STEP file."""
    diameter: float
    center_x: float
    center_y: float
    center_z: float
    depth: float
    is_through: bool


@dataclass
class BossReference:
    """Reference data for a boss feature from the STEP file."""
    diameter: float
    center_x: float
    center_y: float
    height: float
    base_x: float = 0.0
    base_y: float = 0.0


@dataclass
class StepReference:
    """Authoritative geometry extracted from the original STEP file."""
    source_step_path: Optional[Path] = None
    width_x: Optional[float] = None
    depth_y: Optional[float] = None
    height_z: Optional[float] = None
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    holes: List[HoleReference] = field(default_factory=list)
    bosses: List[BossReference] = field(default_factory=list)
    face_count: int = 0
    edge_count: int = 0
    solid_count: int = 0
    extraction_error: Optional[str] = None

    def find_hole(self, diameter: Optional[float] = None,
                  center_2d: Optional[Tuple[float, float]] = None) -> Optional[HoleReference]:
        """Find a hole by diameter (and optionally proximity to 2D position)."""
        candidates = list(self.holes)
        if diameter is not None:
            matched = [h for h in candidates if abs(h.diameter - diameter) < 1.0]
            if matched:
                candidates = matched

        if not candidates:
            return None

        if center_2d:
            candidates.sort(
                key=lambda h: math.hypot(h.center_x - center_2d[0], h.center_y - center_2d[1])
            )
        return candidates[0]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "source": str(self.source_step_path) if self.source_step_path else None,
            "bbox": {
                "width_x": self.width_x,
                "depth_y": self.depth_y,
                "height_z": self.height_z,
            },
            "holes": len(self.holes),
            "bosses": len(self.bosses),
            "error": self.extraction_error,
        }


def extract_step_reference(step_path: Path) -> StepReference:
    """Extract authoritative geometry from a STEP file.

    Parameters
    ----------
    step_path : Path
        Path to the original STEP file.

    Returns
    -------
    StepReference
        Extracted reference data.
    """
    ref = StepReference(source_step_path=step_path)

    try:
        import FreeCAD.Part as Part
    except ImportError:
        ref.extraction_error = "FreeCAD not available"
        return ref

    try:
        shape = Part.Shape()
        shape.read(str(step_path))

        ref.face_count = len(shape.Faces)
        ref.edge_count = len(shape.Edges)
        ref.solid_count = len(shape.Solids)

        bb = shape.BoundBox
        ref.width_x = round(bb.XLength, 4)
        ref.depth_y = round(bb.YLength, 4)
        ref.height_z = round(bb.ZLength, 4)
        ref.origin_x = round(bb.XMin, 4)
        ref.origin_y = round(bb.YMin, 4)
        ref.origin_z = round(bb.ZMin, 4)

        _extract_from_faces(shape, ref)

    except Exception as exc:
        ref.extraction_error = f"STEP extraction failed: {exc}"

    return ref


def _extract_from_faces(shape: Any, ref: StepReference) -> None:
    """Extract cylindrical features from STEP face geometry."""
    try:
        z_min = ref.origin_z
        z_max = ref.origin_z + (ref.height_z or 100)
        z_mid = (z_min + z_max) / 2

        cylinder_faces: List[Dict] = []

        for face in shape.Faces:
            try:
                surf = face.Surface
                if not (hasattr(surf, 'Radius') and hasattr(surf, 'Axis') and hasattr(surf, 'Center')):
                    continue

                radius = surf.Radius
                if radius < 0.5:
                    continue

                axis = surf.Axis
                if abs(axis.z) < 0.9:
                    continue

                center = surf.Center
                bb = face.BoundBox
                cyl_h = round(bb.ZLength, 4)

                cylinder_faces.append({
                    'radius': radius,
                    'diameter': round(radius * 2, 4),
                    'center': (round(center.x, 4), round(center.y, 4), round(center.z, 4)),
                    'z_min': bb.ZMin,
                    'z_max': bb.ZMax,
                    'z_mid': (bb.ZMin + bb.ZMax) / 2,
                    'height': cyl_h,
                })
            except Exception:
                continue

        # Deduplicate
        seen_centers: List[Tuple[float, float]] = []
        for c in cylinder_faces:
            cx, cy = c['center'][0], c['center'][1]
            if not any(math.hypot(cx - sc[0], cy - sc[1]) < 2.0 for sc in seen_centers):
                seen_centers.append((cx, cy))
                _classify_cylinder(c, ref, z_min, z_max, z_mid)

    except Exception:
        pass


def _classify_cylinder(cyl: Dict, ref: StepReference,
                        z_min: float, z_max: float, z_mid: float) -> None:
    """Classify a cylindrical face as hole or boss."""
    cx, cy, cz = cyl['center']
    cz_mid = cyl['z_mid']
    cyl_h = cyl['height']
    d = cyl['diameter']
    full_h = ref.height_z or 100

    if cyl_h >= full_h * 0.8:
        # Spans nearly full height → through-hole
        ref.holes.append(HoleReference(
            diameter=d, center_x=cx, center_y=cy, center_z=cz,
            depth=full_h, is_through=True,
        ))
    elif cz_mid > z_mid:
        # Center above mid-plane → boss
        ref.bosses.append(BossReference(
            diameter=d, center_x=cx, center_y=cy, height=cyl_h,
        ))
    else:
        # Center below mid-plane → through-hole (going up)
        ref.holes.append(HoleReference(
            diameter=d, center_x=cx, center_y=cy, center_z=cz,
            depth=full_h, is_through=True,
        ))


def get_step_reference_path() -> Optional[Path]:
    """Auto-find the original STEP file in input/ directory."""
    input_dir = Path("input")
    if not input_dir.exists():
        return None
    for p in sorted(input_dir.iterdir()):
        if p.suffix.lower() in (".step", ".stp"):
            return p
    return None
