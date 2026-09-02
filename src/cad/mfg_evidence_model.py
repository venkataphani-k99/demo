"""Phase M1 — Manufacturability Evidence Model & Epistemic Taxonomy.

Defines the core data structures for manufacturing findings with strict
distinction between:
- KNOWN_FACT (measured B-Rep geometry, topological entities, exact dimensions)
- INFERRED (manufacturing interpretation, potential side action, sink risk)
- UNKNOWN (variables not determinable from CAD alone like tooling steel, texture, cycle time)
- AMBIGUOUS (features with multiple plausible release strategies)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EpistemicState(str, Enum):
    KNOWN_FACT = "KNOWN_FACT"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


class FindingCategory(str, Enum):
    DRAFT_DEFICIENCY = "DRAFT_DEFICIENCY"
    POTENTIAL_SIDE_ACTION = "POTENTIAL_SIDE_ACTION"
    POSSIBLE_LIFTER_REGION = "POSSIBLE_LIFTER_REGION"
    TRANSVERSE_CORE_PIN = "TRANSVERSE_CORE_PIN"
    THREAD_RELEASE_CONCERN = "THREAD_RELEASE_CONCERN"
    CANDIDATE_PARTING_REGION = "CANDIDATE_PARTING_REGION"
    CORE_CAVITY_SHUTOFF = "CORE_CAVITY_SHUTOFF"
    WALL_THICKNESS_CONCERN = "WALL_THICKNESS_CONCERN"
    RIB_BOSS_PROPORTION = "RIB_BOSS_PROPORTION"
    EJECTION_CONCERN = "EJECTION_CONCERN"


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"    # True undercut or severe zero-draft on deep draw
    WARNING = "WARNING"      # Minor draft deficiency, thick wall transition
    INFO = "INFO"            # Informational feature (core pin, parting segment)
    ACCEPTABLE = "ACCEPTABLE"# Fully compliant feature


@dataclass
class ManufacturingFinding:
    finding_id: str                      # e.g. "MFG_001"
    category: FindingCategory
    severity: SeverityLevel
    knowledge_state: EpistemicState      # KNOWN_FACT vs INFERRED vs AMBIGUOUS
    title: str
    source_entities: List[str]           # ["Face12", "Face13"] or ["Edge45"]
    pull_direction: List[float]          # [0.0, 0.0, 1.0]
    known_geometry: Dict[str, Any]       # Exact numbers: draft_angle_deg, area_mm2, thickness_mm, normal
    engineering_interpretation: str      # Inferred potential impact
    geometric_reasoning: str             # Deterministic justification
    unknowns: List[str]                  # Variables not determinable from CAD alone
    recommended_engineer_action: str     # Review guidance
    confidence: float                    # 0.0 - 1.0
    anchor_point: Optional[List[float]] = None  # [x, y, z] for 3D viewport tagging
    vector: Optional[List[float]] = None        # Direction or stroke vector [dx, dy, dz]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        d["knowledge_state"] = self.knowledge_state.value
        return d


@dataclass
class PullDirectionCandidate:
    candidate_id: str                   # "PULL_DIR_A", "PULL_DIR_B"
    direction_vector: List[float]       # [0.0, 0.0, -1.0]
    direction_name: str                 # "Negative Z (-Z / Bottom-Top)"
    derivation_source: str              # "DOMINANT_PLANAR_NORMAL", "BOUNDING_BOX_AXIS", "CYLINDRICAL_AXIS"
    draft_violation_count: int
    draft_violation_area_mm2: float
    potential_undercut_count: int
    undercut_area_mm2: float
    side_action_candidate_count: int
    lifter_candidate_count: int
    transverse_hole_count: int
    projected_area_mm2: float
    estimated_clamping_tonnage: float
    moldability_score: float            # 0 - 100
    is_geometrically_preferred: bool
    trade_off_analysis: str             # Engineering explanation of why this direction is / is not optimal

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WallThicknessRegion:
    region_id: str
    face_ids: List[str]
    sample_point: List[float]
    measured_thickness_mm: float
    nominal_range_mm: List[float]
    condition: str                      # "THIN_WALL", "THICK_SECTION_SINK_RISK", "ACCEPTABLE"
    thickness_delta_pct: float
    sink_mark_risk_score: float         # 0.0 - 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RibBossFeature:
    feature_id: str
    feature_type: str                   # "BOSS", "RIB", "GUSSET"
    face_ids: List[str]
    root_thickness_mm: float
    nominal_wall_thickness_mm: float
    root_to_wall_ratio: float
    max_recommended_ratio: float
    height_mm: float
    draft_angle_deg: float
    is_compliant: bool
    review_note: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransverseHole:
    hole_id: str
    face_id: str
    diameter_mm: float
    depth_mm: float
    axis_vector: List[float]
    is_through: bool
    angle_to_pull_deg: float
    potential_core_pin_requirement: str  # "TRANSVERSE_CORE_PIN_CANDIDATE", "ALIGNED_WITH_DRAW"
    center_point: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DraftRelevanceBreakdown:
    total_faces: int
    applicable_draw_faces: int
    excluded_planar_caps: int
    excluded_perpendicular_shutoffs: int
    excluded_micro_fillets: int
    ambiguous_faces: int
    valid_draft_warnings: int
    undercut_faces_count: int
    connected_undercut_regions_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectedUndercutRegion:
    region_id: str                      # e.g. "UNDERCUT_REGION_001"
    classification: str                 # "EXTERNAL_UNDERCUT", "INTERNAL_UNDERCUT", "SIDE_HOLE_UNDERCUT"
    source_faces: List[str]
    centroid: List[float]               # [x, y, z]
    total_undercut_area_mm2: float
    mean_normal: List[float]
    slide_vector: List[float]           # Verified S . D_pull = 0
    estimated_clearance_stroke_mm: float
    candidate_mechanism: str            # "POTENTIAL_SLIDER", "POTENTIAL_LIFTER"
    dfm_elimination_advice: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

