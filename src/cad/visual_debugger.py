"""FreeCAD Visual Debugger & Inspection Macro for CAD Intelligence.

Provides visual highlighting of B-Rep entities and recognized CAD features inside FreeCAD GUI:
- Highlight individual Face IDs (e.g. Face17, Face4) in bright red.
- Highlight all Cylindrical faces in cyan.
- Highlight logical Engineering Features (e.g. CBORE_001, HOLE_002, BOSS_004, FILLET_005)
  highlighting all constituent B-Rep faces simultaneously in distinct feature colors.
- Color code the model by surface classification:
    * Planar faces -> Light Green (0.2, 0.8, 0.2)
    * Cylindrical faces -> Cyan (0.0, 0.8, 1.0)
    * Toroidal faces -> Orange (1.0, 0.6, 0.1)
    * B-Spline surfaces -> Magenta (0.9, 0.2, 0.9)

Usage in FreeCAD GUI Python Console:
    from src.cad.visual_debugger import highlight_feature, highlight_face, highlight_cylinders, color_by_surface_type
    highlight_feature("CBORE_001")
    highlight_feature("HOLE_002")
    highlight_feature("BOSS_004")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Import
import Part
from src.cad.features import RecognizedFeature, recognize_cad_features
from src.cad.measurements import MeasurementEngine
from src.cad.topology import build_topology_graph

# Color Palettes (RGBA float tuples 0.0 - 1.0)
COLOR_DEFAULT = (0.8, 0.8, 0.8, 0.0)
COLOR_HIGHLIGHT = (1.0, 0.1, 0.1, 0.0)      # Bright Red
COLOR_CYLINDER = (0.0, 0.8, 1.0, 0.0)       # Cyan
COLOR_PLANE = (0.2, 0.85, 0.3, 0.0)         # Soft Green
COLOR_TORUS = (1.0, 0.55, 0.1, 0.0)         # Warm Orange
COLOR_BSPLINE = (0.85, 0.2, 0.85, 0.0)      # Vivid Magenta
COLOR_DIMMED = (0.3, 0.3, 0.35, 0.0)        # Dim Gray

COLOR_FEATURE_HOLE = (1.0, 0.2, 0.2, 0.0)   # Bright Red
COLOR_FEATURE_CBORE = (1.0, 0.5, 0.0, 0.0)  # Bright Orange
COLOR_FEATURE_BOSS = (0.1, 0.8, 0.3, 0.0)   # Vivid Green
COLOR_FEATURE_FILLET = (0.7, 0.3, 1.0, 0.0) # Purple/Violet


def get_active_part(doc: Optional[Any] = None) -> Tuple[Any, Any]:
    """Retrieve or load active document and primary shape object."""
    if doc is None:
        if FreeCAD.ActiveDocument is not None:
            doc = FreeCAD.ActiveDocument
        else:
            step_file = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
            doc = FreeCAD.newDocument("VisualDebugger")
            Import.insert(str(step_file), doc.Name)
            doc.recompute()

    obj = None
    for o in doc.Objects:
        if hasattr(o, "Shape") and not o.Shape.isNull():
            obj = o
            break

    if obj is None:
        raise RuntimeError("No object with valid B-Rep Shape found in document.")

    return doc, obj


def color_by_surface_type(doc: Optional[Any] = None, obj: Optional[Any] = None) -> None:
    """Color-code all faces of the part by their mathematical surface classification."""
    doc, obj = get_active_part(doc)
    shape = obj.Shape
    face_count = len(shape.Faces)
    colors = []

    for idx, f in enumerate(shape.Faces):
        surf = f.Surface
        type_id = getattr(surf, "TypeId", type(surf).__name__).lower()
        class_name = type(surf).__name__.lower()

        if "cylinder" in type_id or "cylinder" in class_name:
            colors.append(COLOR_CYLINDER)
        elif "plane" in type_id or "plane" in class_name:
            colors.append(COLOR_PLANE)
        elif "toroid" in type_id or "torus" in type_id or "toroid" in class_name:
            colors.append(COLOR_TORUS)
        elif "bspline" in type_id or "bspline" in class_name:
            colors.append(COLOR_BSPLINE)
        else:
            colors.append(COLOR_DEFAULT)

    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.DiffuseColor = colors
        print(f"[VisualDebugger] Color-coded {face_count} faces by surface type.")
    else:
        print("[VisualDebugger] Headless mode: per-face colors calculated successfully.")


def highlight_face(face_id: str | int, doc: Optional[Any] = None, obj: Optional[Any] = None) -> None:
    """Highlight a single Face ID (e.g. 'Face17' or 17) in bright red, dimming others."""
    doc, obj = get_active_part(doc)
    shape = obj.Shape
    face_count = len(shape.Faces)

    if isinstance(face_id, str):
        idx = int(face_id.lower().replace("face", "")) - 1
    else:
        idx = int(face_id) - 1

    if idx < 0 or idx >= face_count:
        raise ValueError(f"Invalid Face index {idx+1}. Valid range: Face1 to Face{face_count}.")

    colors = []
    for i in range(face_count):
        if i == idx:
            colors.append(COLOR_HIGHLIGHT)
        else:
            colors.append(COLOR_DIMMED)

    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.DiffuseColor = colors
        print(f"[VisualDebugger] Highlighted Face{idx+1}.")
    else:
        print(f"[VisualDebugger] Headless mode: Highlighted Face{idx+1}.")


def highlight_cylinders(doc: Optional[Any] = None, obj: Optional[Any] = None) -> None:
    """Highlight all 22 Cylindrical faces in bright cyan, dimming non-cylindrical faces."""
    doc, obj = get_active_part(doc)
    shape = obj.Shape
    face_count = len(shape.Faces)
    colors = []
    cyl_count = 0

    for idx, f in enumerate(shape.Faces):
        surf = f.Surface
        type_id = getattr(surf, "TypeId", type(surf).__name__).lower()
        class_name = type(surf).__name__.lower()

        if "cylinder" in type_id or "cylinder" in class_name:
            colors.append(COLOR_CYLINDER)
            cyl_count += 1
        else:
            colors.append(COLOR_DIMMED)

    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.DiffuseColor = colors
        print(f"[VisualDebugger] Highlighted {cyl_count} Cylindrical faces in cyan.")
    else:
        print(f"[VisualDebugger] Headless mode: Highlighted {cyl_count} Cylindrical faces.")


def highlight_feature(
    feature_or_id: Union[str, RecognizedFeature],
    doc: Optional[Any] = None,
    obj: Optional[Any] = None,
) -> None:
    """Highlight all constituent B-Rep faces of a recognized engineering feature in FreeCAD."""
    doc, obj = get_active_part(doc)
    shape = obj.Shape
    face_count = len(shape.Faces)

    # If string passed, recognize features from shape to resolve
    if isinstance(feature_or_id, str):
        topo = build_topology_graph(shape)
        engine = MeasurementEngine(shape)
        features = recognize_cad_features(shape, topo, engine)
        
        feat_match = None
        for f in features:
            if f.feature_id.lower() == feature_or_id.lower() or f.feature_type.lower() == feature_or_id.lower():
                feat_match = f
                break
        
        if feat_match is None:
            # Try partial matching e.g. "cbore", "hole", "boss"
            for f in features:
                if feature_or_id.lower() in f.feature_id.lower() or feature_or_id.lower() in f.feature_type.lower():
                    feat_match = f
                    break

        if feat_match is None:
            raise ValueError(f"Feature '{feature_or_id}' not found. Available features: {[f.feature_id for f in features]}")
        target_feat = feat_match
    else:
        target_feat = feature_or_id

    # Choose color based on feature type
    if "cbore" in target_feat.feature_id.lower() or "counterbore" in target_feat.feature_type.lower():
        feat_color = COLOR_FEATURE_CBORE
    elif "hole" in target_feat.feature_id.lower() or "bore" in target_feat.feature_type.lower():
        feat_color = COLOR_FEATURE_HOLE
    elif "boss" in target_feat.feature_id.lower():
        feat_color = COLOR_FEATURE_BOSS
    elif "fillet" in target_feat.feature_id.lower() or "blend" in target_feat.feature_type.lower():
        feat_color = COLOR_FEATURE_FILLET
    else:
        feat_color = COLOR_HIGHLIGHT

    target_indices = {
        int(fid.replace("Face", "")) - 1
        for fid in target_feat.source_entities
        if "face" in fid.lower() and fid.replace("Face", "").isdigit()
    }

    colors = []
    for i in range(face_count):
        if i in target_indices:
            colors.append(feat_color)
        else:
            colors.append(COLOR_DIMMED)

    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.DiffuseColor = colors
        print(f"[VisualDebugger] Highlighted feature '{target_feat.feature_id}' ({target_feat.feature_type}) across {len(target_indices)} B-Rep faces: {target_feat.source_entities}")
    else:
        print(f"[VisualDebugger] Headless mode: Highlighted feature '{target_feat.feature_id}' across {target_feat.source_entities}.")


def reset_colors(doc: Optional[Any] = None, obj: Optional[Any] = None) -> None:
    """Reset part appearance to standard CAD gray."""
    doc, obj = get_active_part(doc)
    face_count = len(obj.Shape.Faces)
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.DiffuseColor = [COLOR_DEFAULT] * face_count
        print(f"[VisualDebugger] Reset {face_count} faces to default appearance.")


if __name__ == "__main__":
    print("=" * 60)
    print("FREECAD VISUAL DEBUGGER FOR CAD INTELLIGENCE")
    print("=" * 60)
    d, o = get_active_part()
    color_by_surface_type(d, o)
    highlight_feature("CBORE_001", d, o)
    print("Visual debugger ready.")
    print("=" * 60)
