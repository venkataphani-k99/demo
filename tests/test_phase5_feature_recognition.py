"""Phase 5: Deterministic CAD Feature Recognition Test Suite.

Validates:
1. Logical Cylindrical Feature Grouping (seam merging, multi-face synthesis).
2. Internal vs External Surface Orientation (cavity/hole vs boss/protrusion).
3. Counterbored Hole Recognition (bore Ø5.5mm, counterbore Ø11.0mm, step face Face23).
4. Through Bore / Hole Recognition (horizontal bore Ø10.0mm across Face6, Face7, Face14, Face15).
5. External Boss Recognition (side boss Ø16.0mm on Face17, Face18).
6. Constant-Radius Fillet Recognition (R2.0mm edge blends and corner blends).
7. Feature Validation and Rejection of invalid geometry.
8. Artifact Generation: output/Pieza18_1_features.json & output/Pieza18_1_features.txt.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.analysis.analyzer import analyze_cad_model
from src.analysis.report import export_analysis_reports
from src.cad.features import (
    FeatureRecognizer,
    RecognizedFeature,
    group_logical_cylinders,
    recognize_cad_features,
)
from src.cad.measurements import MeasurementEngine
from src.cad.step_loader import load_step
from src.cad.topology import build_topology_graph


def test_logical_cylinder_grouping(shape, topo, engine) -> None:
    """Validate that 22 raw B-Rep cylindrical faces are synthesized into unified logical cylinders."""
    print("  [TEST] Validating logical cylindrical feature grouping...")
    groups = group_logical_cylinders(shape, topo, engine)
    assert len(groups) == 15, f"Expected 15 logical cylinder groups, got {len(groups)}"

    group_by_faces = {tuple(g.face_ids): g for g in groups}

    # 1. Central Inner Cylinder: Face4 + Face22
    g_inner = group_by_faces.get(("Face4", "Face22"))
    assert g_inner is not None, "Missing logical cylinder for Face4 + Face22"
    assert abs(g_inner.diameter - 5.50) < 1e-4
    assert g_inner.is_internal is True
    assert abs(g_inner.total_sweep_deg - 360.0) < 1e-3

    # 2. Central Counterbore: Face5 + Face21
    g_cbore = group_by_faces.get(("Face5", "Face21"))
    assert g_cbore is not None, "Missing logical cylinder for Face5 + Face21"
    assert abs(g_cbore.diameter - 11.00) < 1e-4
    assert g_cbore.is_internal is True
    assert abs(g_cbore.total_sweep_deg - 360.0) < 1e-3

    # 3. Horizontal Bore: Face6 + Face7 + Face14 + Face15
    g_bore = group_by_faces.get(("Face6", "Face7", "Face14", "Face15"))
    assert g_bore is not None, "Missing logical cylinder for Face6 + Face7 + Face14 + Face15"
    assert abs(g_bore.diameter - 10.00) < 1e-4
    assert g_bore.is_internal is True
    assert abs(g_bore.total_sweep_deg - 360.0) < 1e-3

    # 4. Side Boss: Face17 + Face18
    g_boss = group_by_faces.get(("Face17", "Face18"))
    assert g_boss is not None, "Missing logical cylinder for Face17 + Face18"
    assert abs(g_boss.diameter - 16.00) < 1e-4
    assert g_boss.is_internal is False

    print("         Logical grouping verified: Multi-face seams successfully synthesized into single features.")


def test_counterbore_recognition(features) -> None:
    """Validate deterministic counterbore recognition on Pieza18_1.STEP."""
    print("  [TEST] Validating counterbore recognition...")
    cbore_feats = [f for f in features if f.feature_type == "counterbored_hole"]
    assert len(cbore_feats) == 1, f"Expected 1 counterbored hole, got {len(cbore_feats)}"

    cbore = cbore_feats[0]
    assert cbore.status == "confirmed"
    assert cbore.confidence >= 0.95
    assert abs(cbore.dimensions["bore_diameter"] - 5.50) < 1e-4
    assert abs(cbore.dimensions["counterbore_diameter"] - 11.00) < 1e-4
    assert abs(cbore.dimensions["bore_depth"] - 3.30) < 1e-2
    assert abs(abs(cbore.axis[2]) - 1.0) < 1e-3  # Z-axis aligned (either +Z or -Z)

    # Verify supporting faces contain inner hole, outer counterbore, and step face
    supporting = set(cbore.source_entities)
    assert {"Face4", "Face22", "Face5", "Face21", "Face23"}.issubset(supporting)

    print(f"         Counterbore verified: Ø{cbore.dimensions['bore_diameter']:.1f}mm bore stepped to Ø{cbore.dimensions['counterbore_diameter']:.1f}mm via Face23.")


def test_through_hole_and_bore_recognition(features) -> None:
    """Validate horizontal through-bore recognition."""
    print("  [TEST] Validating through-bore recognition...")
    hole_feats = [f for f in features if f.feature_type == "through_hole"]
    assert len(hole_feats) >= 1, "Expected at least 1 through-hole feature"

    h = hole_feats[0]
    assert h.status == "confirmed"
    assert abs(h.dimensions["diameter"] - 10.00) < 1e-4
    assert abs(h.axis[0] - 1.0) < 1e-3  # X-axis aligned
    assert set(h.source_entities) == {"Face6", "Face7", "Face14", "Face15"}

    print("         Horizontal through-bore verified: Ø10.0mm spanning Face6, Face7, Face14, Face15.")


def test_boss_and_fillet_recognition(features) -> None:
    """Validate external boss and fillet recognition."""
    print("  [TEST] Validating boss and fillet recognition...")
    boss_feats = [f for f in features if f.feature_type == "external_boss"]
    assert len(boss_feats) >= 1, "Expected at least 1 external boss"

    b = boss_feats[0]
    assert b.status == "confirmed"
    assert abs(b.dimensions["diameter"] - 16.00) < 1e-4
    assert set(b.source_entities) == {"Face17", "Face18"}

    fillet_feats = [f for f in features if "fillet" in f.feature_type or "blend" in f.feature_type]
    assert len(fillet_feats) >= 10, f"Expected at least 10 fillets, got {len(fillet_feats)}"

    for f in fillet_feats:
        assert f.status == "confirmed"
        assert abs(f.dimensions["radius"] - 2.00) < 1e-4

    print(f"         External boss (Ø16.0mm) and {len(fillet_feats)} constant-radius (R2.0mm) fillets verified.")


def test_feature_validation_and_rejection(shape, topo, engine) -> None:
    """Validate that invalid features are properly caught and marked as rejected."""
    print("  [TEST] Validating feature rejection logic...")
    recognizer = FeatureRecognizer(shape, topo, engine)

    # Inject an invalid counterbore where bore >= counterbore
    bad_cbore = RecognizedFeature(
        feature_id="CBORE_BAD",
        feature_type="counterbored_hole",
        source_entities=["Face4", "Face5"],
        dimensions={"bore_diameter": 15.0, "counterbore_diameter": 10.0},
    )
    recognizer.recognized_features.append(bad_cbore)
    recognizer._validate_features()
    assert bad_cbore.status == "rejected", "Expected invalid counterbore to be rejected"
    assert "bore diameter" in bad_cbore.notes[0].lower()

    # Inject an invalid feature with non-existent entity
    bad_entity_feat = RecognizedFeature(
        feature_id="HOLE_BAD",
        feature_type="through_hole",
        source_entities=["Face9999"],
        dimensions={"diameter": 10.0},
    )
    recognizer.recognized_features.append(bad_entity_feat)
    recognizer._validate_features()
    assert bad_entity_feat.status == "rejected", "Expected non-existent entity to be rejected"

    print("         Rejection logic verified for invalid dimensions and non-existent entities.")


def test_report_artifacts(analysis, output_dir: Path) -> None:
    """Validate export of features JSON and text reports."""
    print("  [TEST] Validating dedicated feature report artifacts...")
    json_path, txt_path, feat_json, feat_txt = export_analysis_reports(analysis, output_dir)
    assert feat_json.exists() and feat_json.stat().st_size > 0
    assert feat_txt.exists() and feat_txt.stat().st_size > 0

    with open(feat_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["filename"] == analysis.filename
        assert "features" in data
        assert len(data["features"]) >= 15
        assert "logical_cylinders" in data

    with open(feat_txt, "r", encoding="utf-8") as f:
        content = f.read()
        assert "CAD MODEL RECOGNIZED ENGINEERING FEATURES REPORT (PHASE 5)" in content
        assert "Counterbored Hole" in content
        assert "Through Hole" in content
        assert "External Boss" in content
        assert "Fillet" in content

    print(f"         Features JSON validated: {feat_json.name} ({feat_json.stat().st_size:,} bytes)")
    print(f"         Features Text validated: {feat_txt.name} ({feat_txt.stat().st_size:,} bytes)")


def run_all_tests() -> bool:
    print("=" * 60)
    print("PHASE 5 — DETERMINISTIC FEATURE RECOGNITION TEST SUITE")
    print("=" * 60)

    step_file = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
    output_dir = PROJECT_ROOT / "output"

    if not step_file.exists():
        print(f"[ERROR] STEP file not found: {step_file}", file=sys.stderr)
        return False

    load_res = load_step(step_file)
    try:
        shape = load_res.primary_shape
        topo = build_topology_graph(shape)
        engine = MeasurementEngine(shape, units="mm")

        test_logical_cylinder_grouping(shape, topo, engine)

        features = recognize_cad_features(shape, topo, engine)
        test_counterbore_recognition(features)
        test_through_hole_and_bore_recognition(features)
        test_boss_and_fillet_recognition(features)
        test_feature_validation_and_rejection(shape, topo, engine)

        analysis = analyze_cad_model(load_res)
        test_report_artifacts(analysis, output_dir)

        print("=" * 60)
        print("ALL PHASE 5 TESTS PASSED SUCCESSFULLY.")
        print("=" * 60)
        return True
    finally:
        load_res.close()


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        sys.exit(1)
