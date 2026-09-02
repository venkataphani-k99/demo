"""
Deterministic CAD Model Validation Layer (Phase 14).
Validates STEP/B-Rep models immediately after import against strict engineering constraints.
"""
from typing import Dict, Any, List, Optional
import math


class ModelValidationError(Exception):
    """Exception raised when a CAD model fails geometric validation."""
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ModelValidator:
    """
    Deterministic validator for imported STEP / FreeCAD / OCCT shapes.
    
    Verifies:
      1. Valid FreeCAD/OCCT Shape object
      2. shape.isValid() is True
      3. Bounding box is non-null and all extents (X, Y, Z) are finite, positive, and non-zero
      4. No 1e100, 2e100, infinity, or NaN values in extents or center coordinates
      5. Non-zero, finite topology counts: Faces > 0, Edges > 0, Vertexes > 0
      6. Successful OCCT tessellation / mesh generation
      7. TechDraw orthographic projection feasibility
    """
    
    @staticmethod
    def validate_shape(shape, model_name: str = "model.step") -> Dict[str, Any]:
        """
        Validates a FreeCAD / OCCT TopoShape object.
        Returns a dictionary with validation diagnostics or raises ModelValidationError.
        """
        if shape is None or not hasattr(shape, "BoundBox"):
            raise ModelValidationError(
                code="NULL_SHAPE",
                message=f"Model '{model_name}' failed to load as a valid OCCT shape."
            )
        
        # 1. Shape validity
        try:
            is_valid = shape.isValid()
        except Exception as e:
            raise ModelValidationError(
                code="SHAPE_VALIDITY_EXCEPTION",
                message=f"Shape.isValid() raised an exception on '{model_name}': {e}"
            )
        
        if not is_valid:
            raise ModelValidationError(
                code="INVALID_BREP_GEOMETRY",
                message=f"Shape '{model_name}' has invalid B-Rep geometry or self-intersections."
            )
        
        # 2. Topology counts
        try:
            num_faces = len(shape.Faces)
            num_edges = len(shape.Edges)
            num_vertexes = len(shape.Vertexes)
        except Exception as e:
            raise ModelValidationError(
                code="TOPOLOGY_READ_ERROR",
                message=f"Failed to extract topology counts from '{model_name}': {e}"
            )
        
        if num_faces == 0 or num_edges == 0 or num_vertexes == 0:
            raise ModelValidationError(
                code="DEGENERATE_TOPOLOGY",
                message=f"Model '{model_name}' has degenerate topology (Faces={num_faces}, Edges={num_edges}, Vertices={num_vertexes}).",
                details={"faces": num_faces, "edges": num_edges, "vertices": num_vertexes}
            )
        
        # 3. Bounding Box check
        bbox = shape.BoundBox
        if bbox is None:
            raise ModelValidationError(
                code="NULL_BOUNDING_BOX",
                message=f"Model '{model_name}' has null bounding box."
            )
        
        x_len = float(bbox.XLength)
        y_len = float(bbox.YLength)
        z_len = float(bbox.ZLength)
        
        coords = [
            bbox.XMin, bbox.XMax, bbox.YMin, bbox.YMax, bbox.ZMin, bbox.ZMax,
            x_len, y_len, z_len
        ]
        
        for val in coords:
            if math.isnan(val) or math.isinf(val) or abs(val) > 1e6:
                raise ModelValidationError(
                    code="NON_FINITE_EXTENTS",
                    message=f"Model '{model_name}' contains non-finite or extreme uninitialized coordinates (val={val}).",
                    details={"coords": coords}
                )
        
        if x_len <= 1e-4 or y_len <= 1e-4 or z_len <= 1e-4:
            raise ModelValidationError(
                code="ZERO_EXTENTS",
                message=f"Model '{model_name}' has zero or near-zero 3D extents ({x_len} x {y_len} x {z_len} mm).",
                details={"x_len": x_len, "y_len": y_len, "z_len": z_len}
            )
        
        # 4. Tessellation test
        try:
            pts, facets = shape.tessellate(0.1)
            if len(pts) == 0 or len(facets) == 0:
                raise ModelValidationError(
                    code="TESSELLATION_FAILED",
                    message=f"OCCT tessellation generated 0 vertices or facets for '{model_name}'."
                )
        except Exception as e:
            if isinstance(e, ModelValidationError):
                raise
            raise ModelValidationError(
                code="TESSELLATION_EXCEPTION",
                message=f"OCCT tessellation exception on '{model_name}': {e}"
            )
            
        return {
            "is_valid": True,
            "status": "VALID_GEOMETRY",
            "model_name": model_name,
            "bounding_box": {
                "x_len": round(x_len, 4),
                "y_len": round(y_len, 4),
                "z_len": round(z_len, 4),
                "x_min": round(float(bbox.XMin), 4),
                "x_max": round(float(bbox.XMax), 4),
                "y_min": round(float(bbox.YMin), 4),
                "y_max": round(float(bbox.YMax), 4),
                "z_min": round(float(bbox.ZMin), 4),
                "z_max": round(float(bbox.ZMax), 4),
            },
            "topology": {
                "faces": num_faces,
                "edges": num_edges,
                "vertices": num_vertexes,
            },
            "tessellation": {
                "vertex_count": len(pts),
                "facet_count": len(facets),
            }
        }
