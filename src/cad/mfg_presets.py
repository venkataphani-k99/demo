"""Phase M1 — Manufacturing & Moldability Process Presets Configuration.

Defines configuration data for various manufacturing and molding processes.
These presets modify analysis assumptions only (draft requirements, nominal walls,
rib ratios, cavity pressures). They do NOT replace deterministic geometry.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProcessPreset:
    preset_id: str
    display_name: str
    description: str
    category: str  # "PLASTIC_INJECTION", "DIE_CASTING", "COMPRESSION", "LSR", "BLOW_MOLDING"
    min_draft_deg: float
    nominal_draft_deg: float
    cavity_pressure_bar: float
    nominal_wall_thickness_min_mm: float
    nominal_wall_thickness_max_mm: float
    max_thickness_variation_pct: float
    max_rib_root_to_wall_ratio: float
    max_boss_wall_to_main_wall_ratio: float
    min_radius_mm: float
    is_extensible: bool = True
    typical_materials: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Default Industrial Process Presets Matrix
PROCESS_PRESETS: Dict[str, ProcessPreset] = {
    "GENERAL_PLASTIC_INJECTION": ProcessPreset(
        preset_id="GENERAL_PLASTIC_INJECTION",
        display_name="General Thermoplastic Injection",
        description="Standard 2-plate / multi-cavity injection molding for untextured plastic resins (PP, PE, ABS, PC, POM).",
        category="PLASTIC_INJECTION",
        min_draft_deg=0.5,
        nominal_draft_deg=1.5,
        cavity_pressure_bar=400.0,
        nominal_wall_thickness_min_mm=1.2,
        nominal_wall_thickness_max_mm=3.5,
        max_thickness_variation_pct=25.0,
        max_rib_root_to_wall_ratio=0.60,
        max_boss_wall_to_main_wall_ratio=0.65,
        min_radius_mm=0.5,
        typical_materials=["ABS", "Polypropylene (PP)", "Polycarbonate (PC)", "POM (Acetal)", "HIPS"],
    ),
    "TEXTURED_PLASTIC_INJECTION": ProcessPreset(
        preset_id="TEXTURED_PLASTIC_INJECTION",
        display_name="Textured / Grain Surface Injection",
        description="Injection molding for parts requiring mold-tech or VDI spark erosion grain finishes (requires +1.5° draft per 0.025mm texture depth).",
        category="PLASTIC_INJECTION",
        min_draft_deg=2.5,
        nominal_draft_deg=3.5,
        cavity_pressure_bar=500.0,
        nominal_wall_thickness_min_mm=1.5,
        nominal_wall_thickness_max_mm=4.0,
        max_thickness_variation_pct=20.0,
        max_rib_root_to_wall_ratio=0.50,
        max_boss_wall_to_main_wall_ratio=0.60,
        min_radius_mm=0.8,
        typical_materials=["Automotive ABS", "PC/ABS Blend", "PA66 (Nylon 6,6)", "PBT"],
    ),
    "HIGH_PRESSURE_DIE_CASTING": ProcessPreset(
        preset_id="HIGH_PRESSURE_DIE_CASTING",
        display_name="High-Pressure Die Casting (HPDC)",
        description="High-pressure hot/cold chamber die casting for aluminum, zinc, and magnesium alloys with high thermal contraction.",
        category="DIE_CASTING",
        min_draft_deg=1.5,
        nominal_draft_deg=2.5,
        cavity_pressure_bar=700.0,
        nominal_wall_thickness_min_mm=2.0,
        nominal_wall_thickness_max_mm=6.0,
        max_thickness_variation_pct=30.0,
        max_rib_root_to_wall_ratio=0.70,
        max_boss_wall_to_main_wall_ratio=0.75,
        min_radius_mm=1.5,
        typical_materials=["Aluminum A380", "Aluminum ADC12", "Zinc Zamak 3", "Magnesium AZ91D"],
    ),
    "SMC_COMPRESSION_MOLDING": ProcessPreset(
        preset_id="SMC_COMPRESSION_MOLDING",
        display_name="SMC / BMC Composite Compression",
        description="Sheet Molding Compound (SMC) heated platen compression molding with vertical shear edges.",
        category="COMPRESSION",
        min_draft_deg=1.5,
        nominal_draft_deg=3.0,
        cavity_pressure_bar=100.0,
        nominal_wall_thickness_min_mm=2.5,
        nominal_wall_thickness_max_mm=8.0,
        max_thickness_variation_pct=35.0,
        max_rib_root_to_wall_ratio=0.75,
        max_boss_wall_to_main_wall_ratio=0.80,
        min_radius_mm=2.0,
        typical_materials=["Vinyl Ester SMC", "Polyester BMC", "Carbon SMC"],
    ),
    "LSR_INJECTION_MOLDING": ProcessPreset(
        preset_id="LSR_INJECTION_MOLDING",
        display_name="Liquid Silicone Rubber (LSR)",
        description="Cold deck liquid silicone rubber injection into heated cavities with flash-sensitive tight shutoffs.",
        category="LSR",
        min_draft_deg=0.0,
        nominal_draft_deg=0.5,
        cavity_pressure_bar=150.0,
        nominal_wall_thickness_min_mm=0.5,
        nominal_wall_thickness_max_mm=5.0,
        max_thickness_variation_pct=40.0,
        max_rib_root_to_wall_ratio=0.80,
        max_boss_wall_to_main_wall_ratio=0.80,
        min_radius_mm=0.3,
        typical_materials=["Optical Silicone", "Medical Grade LSR 40-70 Shore A"],
    ),
}


def get_process_preset(preset_id: str) -> ProcessPreset:
    """Returns the requested process profile or defaults to GENERAL_PLASTIC_INJECTION."""
    return PROCESS_PRESETS.get(preset_id, PROCESS_PRESETS["GENERAL_PLASTIC_INJECTION"])


def list_process_presets() -> List[Dict[str, Any]]:
    """Returns list of available process profiles for API consumption."""
    return [p.to_dict() for p in PROCESS_PRESETS.values()]
