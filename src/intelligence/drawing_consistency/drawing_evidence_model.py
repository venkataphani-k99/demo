"""Phase 25 — Drawing Evidence Model.

Defines pure data models for 2D engineering drawing evidence.
Enforces that raw drawing facts (nominal values, tolerances, GD&T symbols,
engineering notes) are captured without premature semantic CAD conversion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConsistencyStatus(str, Enum):
    CONSISTENT = "CONSISTENT"              # 🟢 Nominal agrees within interpretation
    CONFLICT = "CONFLICT"                  # 🔴 Engineering definition discrepancy
    CANNOT_VERIFY = "CANNOT_VERIFY"        # 🟡 Information not determinable from CAD (e.g. material)
    MISSING = "MISSING"                    # 🟠 Important CAD geometry not dimensioned on drawing
    AMBIGUOUS = "AMBIGUOUS"                # 🟣 Multiple geometric candidates for 1 callout


class MatchStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROBABLE = "PROBABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


@dataclass
class DrawingDimensionItem:
    dimension_id: str                      # e.g. "DRAW_DIM_001"
    dimension_type: str                    # "DIAMETER", "LINEAR", "RADIUS", "DISTANCE", "ANGULAR"
    nominal_value: float                   # e.g. 23.00
    tolerance_raw: Optional[str] = None    # e.g. "±0.02" or "+0.05/-0.00"
    tolerance_plus: Optional[float] = None
    tolerance_minus: Optional[float] = None
    units: str = "mm"
    assigned_view: str = "FRONT"           # "FRONT", "TOP", "RIGHT", "SECTION_AA", "DETAIL"
    text_raw: str = "Ø23.00"
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0]) # [x, y, w, h]
    confidence: float = 1.0
    source_page: int = 1
    source_region: str = "MAIN_VIEW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingGDTItem:
    gdt_id: str                            # e.g. "DRAW_GDT_001"
    symbol: str                            # "POSITION", "PERPENDICULARITY", "FLATNESS", "CONCENTRICITY"
    tolerance_value: float
    datum_refs: List[str] = field(default_factory=list) # ["A", "B"]
    assigned_view: str = "FRONT"
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    text_raw: str = ""
    confidence: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingNoteItem:
    note_id: str                           # e.g. "DRAW_NOTE_001"
    category: str                          # "MATERIAL", "HEAT_TREAT", "SURFACE_FINISH", "THREAD", "GENERAL_TOL"
    text_raw: str
    inferred_standard: Optional[str] = None
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingSectionItem:
    section_id: str                        # e.g. "DRAW_SEC_AA"
    section_label: str                     # "SECTION A-A"
    view_name: str                         # "SECTION_AA"
    cutting_plane_hint: str = "Z_AXIS"     # "Z_AXIS", "X_AXIS", "Y_AXIS"
    exposed_feature_hints: List[str] = field(default_factory=list)
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingEvidencePackage:
    drawing_filename: str
    drawing_format: str                    # "SVG", "PDF", "PNG"
    title_block_part_number: Optional[str] = None
    title_block_material: Optional[str] = None
    dimensions: List[DrawingDimensionItem] = field(default_factory=list)
    gdt_items: List[DrawingGDTItem] = field(default_factory=list)
    notes: List[DrawingNoteItem] = field(default_factory=list)
    sections: List[DrawingSectionItem] = field(default_factory=list)
    views_detected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CADDrawingMatchItem:
    match_id: str                          # e.g. "MATCH_001"
    cad_feature_id: Optional[str] = None   # e.g. "FEAT_001"
    cad_entity_id: Optional[str] = None    # e.g. "Face2"
    cad_entity_type: str = "FACE"          # "FACE", "EDGE", "SOLID", "SECTION"
    cad_nominal_value: float = 0.0
    cad_property: str = "diameter_mm"      # "diameter_mm", "length_mm", "width_mm", "radius_mm"
    cad_measurement_method: str = "OCCT_GeomCylinder_Radius"
    
    drawing_evidence_id: Optional[str] = None # e.g. "DRAW_DIM_001"
    drawing_nominal_value: Optional[float] = None
    drawing_tolerance_raw: Optional[str] = None
    drawing_text_raw: Optional[str] = None
    drawing_view: Optional[str] = None
    drawing_bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    consistency_status: ConsistencyStatus = ConsistencyStatus.CONSISTENT
    numerical_delta_mm: float = 0.0
    match_confidence: float = 1.0
    match_reason: str = "Exact geometric diameter match in Front View"
    
    epistemic_provenance: str = "CAD: Face2 (OCCT GeomCylinder) vs Drawing: DRAW_DIM_001"
    engineering_rationale: str = "Nominal geometry matches drawing within 0.001mm."
    recommended_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["consistency_status"] = self.consistency_status.value
        return d


@dataclass
class ConsistencyAuditSummary:
    total_cad_features_audited: int
    total_drawing_dimensions_found: int
    matched_count: int
    consistent_count: int
    conflict_count: int
    cannot_verify_count: int
    missing_count: int
    ambiguous_count: int
    dimension_coverage_percent: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
