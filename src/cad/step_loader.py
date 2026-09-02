"""STEP file loader and validation module for FreeCAD.

Provides robust loading of STEP/STP CAD files, extracts header metadata/units,
and instantiates native FreeCAD/OCCT B-Rep shapes.
"""
from __future__ import annotations

import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure FreeCAD environment is initialized
import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Import
import Part


class CadImportError(Exception):
    """Raised when CAD import or STEP loading fails."""
    pass


class InvalidExtensionError(CadImportError):
    """Raised when file extension is not a supported STEP format."""
    pass


@dataclass
class StepMetadata:
    """Header metadata extracted directly from STEP file."""
    schema: str = "UNKNOWN"
    originating_system: str = "UNKNOWN"
    timestamp: str = "UNKNOWN"
    file_description: str = "UNKNOWN"
    units: str = "mm"


@dataclass
class StepLoadResult:
    """Container for the loaded STEP model and its FreeCAD document."""
    file_path: Path
    file_name: str
    file_size_bytes: int
    doc_name: str
    doc: Any  # FreeCAD Document
    objects: List[Any]  # List of FreeCAD feature objects
    primary_shape: Optional[Any]  # Merged or primary Part::TopoShape
    metadata: StepMetadata
    is_valid: bool = True
    error_message: Optional[str] = None

    def close(self) -> None:
        """Cleanly close and free the FreeCAD document."""
        if self.doc and self.doc_name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc_name)


def parse_step_header(file_path: Path) -> StepMetadata:
    """Parse header metadata and units directly from the STEP physical file."""
    metadata = StepMetadata()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Read first 150 lines which contain HEADER and initial DATA context
            header_lines = [f.readline() for _ in range(150)]
            header_text = "".join(header_lines)

        # 1. Schema
        schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", header_text, re.IGNORECASE)
        if schema_match:
            metadata.schema = schema_match.group(1)

        # 2. Originating System / Preprocessor
        orig_match = re.search(r"FILE_NAME\s*\([^,]+,[^,]+,\s*\([^)]*\),\s*\([^)]*\),\s*'([^']*)',\s*'([^']*)'", header_text, re.IGNORECASE)
        if orig_match:
            sw_name = orig_match.group(1).strip()
            sw_system = orig_match.group(2).strip()
            metadata.originating_system = f"{sw_name} ({sw_system})".strip(" ()")

        # 3. Timestamp
        time_match = re.search(r"FILE_NAME\s*\([^,]+,\s*'([^']+)'", header_text, re.IGNORECASE)
        if time_match:
            metadata.timestamp = time_match.group(1)

        # 4. Description
        desc_match = re.search(r"FILE_DESCRIPTION\s*\(\s*\(\s*'([^']+)'", header_text, re.IGNORECASE)
        if desc_match:
            metadata.file_description = desc_match.group(1)

        # 5. Length Unit Detection (SI_UNIT .MILLI., .METRE., INCH, etc.)
        if ".MILLI." in header_text and ".METRE." in header_text:
            metadata.units = "mm"
        elif ".CENTI." in header_text and ".METRE." in header_text:
            metadata.units = "cm"
        elif ".METRE." in header_text and not any(p in header_text for p in [".MILLI.", ".CENTI.", ".MICRO."]):
            metadata.units = "m"
        elif "INCH" in header_text:
            metadata.units = "in"
        else:
            # Default CAD standard in FreeCAD/OCCT
            metadata.units = "mm"

    except Exception:
        # Fallback to defaults if header parsing encounters non-standard formatting
        pass

    return metadata


def load_step(file_path: str | Path) -> StepLoadResult:
    """Validate and import a STEP/STP file into a FreeCAD document.

    Args:
        file_path: Absolute or relative path to the STEP file.

    Returns:
        StepLoadResult containing the FreeCAD document and B-Rep shape.

    Raises:
        FileNotFoundError: If the file does not exist.
        InvalidExtensionError: If the file is not a .step or .stp file.
        CadImportError: If FreeCAD fails to parse or build the B-Rep shape.
    """
    path = Path(file_path).resolve()

    # 1. Validate file existence
    if not path.exists():
        raise FileNotFoundError(f"STEP file not found at: {path}")

    if not path.is_file():
        raise CadImportError(f"Path is not a regular file: {path}")

    # 2. Validate file extension
    valid_extensions = {".step", ".stp", ".stpz", ".iges", ".igs", ".brep", ".brp", ".fcstd"}
    ext = path.suffix.lower()
    if ext not in valid_extensions:
        raise InvalidExtensionError(
            f"Invalid file extension '{path.suffix}'. Supported extensions are: {', '.join(sorted(valid_extensions))}"
        )

    # 3. Check file size
    file_size = path.stat().st_size
    if file_size == 0:
        raise CadImportError(f"CAD file is empty (0 bytes): {path}")

    # 4. Extract header metadata (if STEP)
    metadata = parse_step_header(path) if ext in {".step", ".stp", ".stpz"} else StepMetadata(schema=ext.upper().lstrip("."))

    # 5. Create unique FreeCAD document for isolation
    doc_name = f"Doc_{path.stem}_{uuid.uuid4().hex[:8]}"

    try:
        if ext == ".fcstd":
            doc = FreeCAD.openDocument(str(path))
            doc_name = doc.Name
        else:
            doc = FreeCAD.newDocument(doc_name)
            if ext in {".step", ".stp", ".stpz", ".iges", ".igs"}:
                Import.insert(str(path), doc.Name)
            elif ext in {".brep", ".brp"}:
                shape_raw = Part.read(str(path))
                feat = doc.addObject("Part::Feature", "BRep_Body")
                feat.Shape = shape_raw

            doc.recompute()

        # 7. Inspect loaded objects
        objects = list(doc.Objects)
        if not objects:
            raise CadImportError(f"No CAD objects were generated from file: {path.name}")

        # Collect shapes from objects (filter out infinite datum planes/axes)
        finite_objs = [
            obj for obj in objects
            if hasattr(obj, "Shape") and not obj.Shape.isNull()
            and abs(obj.Shape.BoundBox.XLength) < 1e6
            and abs(obj.Shape.BoundBox.YLength) < 1e6
            and abs(obj.Shape.BoundBox.ZLength) < 1e6
            and len(obj.Shape.Faces) > 0
        ]
        if not finite_objs:
            raise CadImportError(f"No valid B-Rep shapes found in CAD model: {path.name}")

        # Check for top-level root assembly parts (e.g. App::Part or Part::Compound containing multiple placed solids)
        multi_solid_containers = [
            obj for obj in finite_objs
            if getattr(obj, "TypeId", "") in ("App::Part", "Part::Compound") and len(obj.Shape.Solids) > 1
        ]

        if multi_solid_containers:
            # Root assembly object has the maximum solid count / face count
            root_assembly = max(multi_solid_containers, key=lambda o: len(o.Shape.Solids))
            primary_shape = root_assembly.Shape
        else:
            solids = [obj for obj in finite_objs if obj.Shape.ShapeType == "Solid"]
            if len(solids) == 1:
                primary_shape = solids[0].Shape
            elif len(solids) > 1:
                placed_shapes = []
                for o in solids:
                    shp = o.Shape.copy()
                    if hasattr(o, "Placement") and o.Placement:
                        shp.Placement = o.Placement
                    placed_shapes.append(shp)
                primary_shape = Part.makeCompound(placed_shapes)
            else:
                primary_shape = finite_objs[0].Shape if len(finite_objs) == 1 else Part.makeCompound([o.Shape for o in finite_objs])

        return StepLoadResult(
            file_path=path,
            file_name=path.name,
            file_size_bytes=file_size,
            doc_name=doc_name,
            doc=doc,
            objects=objects,
            primary_shape=primary_shape,
            metadata=metadata,
            is_valid=True,
        )

    except Exception as e:
        # Clean up document on failure
        if doc_name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(doc_name)
        if isinstance(e, CadImportError):
            raise
        raise CadImportError(f"Failed to load CAD file '{path.name}': {str(e)}") from e

