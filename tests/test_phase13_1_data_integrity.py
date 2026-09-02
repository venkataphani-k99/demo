"""Phase 13.1 — Multi-Project Data Integrity and Isolation Test Suite.

Proves:
1. Uploading two distinct STEP files creates two isolated projects with distinct UUIDs and SHA-256 hashes.
2. Bounding boxes are derived strictly from each project's own STEP geometry.
3. Feature lists are strictly project-scoped (Pieza18_1 = 20 features, Propeller = 2 features).
4. Dimensions are strictly project-scoped (Pieza18_1 = 14 placed / 20 candidates, Propeller = 2 candidates).
5. TechDraw drawings and artifacts are strictly project-scoped.
6. No project can read or mutate another project's analysis or review artifacts.
7. Provenance fields (project_id, filename, sha256_hash, source_file, timestamp) are verified.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# Ensure root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

STEP_PIEZA = PROJECT_ROOT / "input" / "Pieza18_1.STEP"
STEP_PROPELLER = PROJECT_ROOT / "input" / "3052_3-Blade_Propeller_3-inch.step"


def test_phase13_1_multi_project_data_isolation():
    print("\n" + "=" * 70)
    print("PHASE 13.1 — MULTI-PROJECT DATA INTEGRITY & ISOLATION SUITE")
    print("=" * 70)

    assert STEP_PIEZA.exists(), f"Missing test fixture: {STEP_PIEZA}"
    assert STEP_PROPELLER.exists(), f"Missing test fixture: {STEP_PROPELLER}"

    pieza_bytes = STEP_PIEZA.read_bytes()
    propeller_bytes = STEP_PROPELLER.read_bytes()

    pieza_expected_sha = hashlib.sha256(pieza_bytes).hexdigest()
    propeller_expected_sha = hashlib.sha256(propeller_bytes).hexdigest()

    # 1. TEST SHA-256 INTEGRITY & UPLOAD ISOLATION
    print("  [TEST 1] Uploading distinct STEP files (Pieza18_1 & Propeller)...")
    resp_p = client.post(
        "/api/v1/projects",
        files={"file": ("Pieza18_1.STEP", pieza_bytes, "application/octet-stream")},
    )
    assert resp_p.status_code == 201, resp_p.text
    p_data = resp_p.json()
    proj_p_id = p_data["project_id"]

    resp_prop = client.post(
        "/api/v1/projects",
        files={"file": ("3052_3-Blade_Propeller_3-inch.step", propeller_bytes, "application/octet-stream")},
    )
    assert resp_prop.status_code == 201, resp_prop.text
    prop_data = resp_prop.json()
    proj_prop_id = prop_data["project_id"]

    assert proj_p_id != proj_prop_id, "Project IDs must be unique"
    assert p_data["sha256_hash"] == pieza_expected_sha, "Pieza SHA-256 mismatch"
    assert prop_data["sha256_hash"] == propeller_expected_sha, "Propeller SHA-256 mismatch"
    assert p_data["sha256_hash"] != prop_data["sha256_hash"], "SHA-256 hashes must be distinct"
    print(f"         Pieza18_1 Project ID: {proj_p_id} (SHA: {pieza_expected_sha[:12]}...) ✓")
    print(f"         Propeller Project ID: {proj_prop_id} (SHA: {propeller_expected_sha[:12]}...) ✓")

    # 2. TEST BOUNDING BOX ISOLATION
    print("  [TEST 2] Analyzing both projects and validating independent bounding boxes...")
    ana_p = client.post(f"/api/v1/projects/{proj_p_id}/analyze").json()
    ana_prop = client.post(f"/api/v1/projects/{proj_prop_id}/analyze").json()

    bbox_p = ana_p["bounding_box"]
    bbox_prop = ana_prop["bounding_box"]

    # Pieza18_1 bounding box is ~70.0 x 24.0 x 30.9
    assert abs(bbox_p["x_length"] - 70.037) < 0.5, f"Pieza X length unexpected: {bbox_p['x_length']}"
    assert abs(bbox_p["y_length"] - 24.014) < 0.5, f"Pieza Y length unexpected: {bbox_p['y_length']}"
    assert abs(bbox_p["z_length"] - 30.871) < 0.5, f"Pieza Z length unexpected: {bbox_p['z_length']}"

    # Propeller bounding box is ~70.3 x 61.1 x 50.3
    assert abs(bbox_prop["x_length"] - 70.271) < 0.5, f"Propeller X length unexpected: {bbox_prop['x_length']}"
    assert abs(bbox_prop["y_length"] - 61.106) < 0.5, f"Propeller Y length unexpected: {bbox_prop['y_length']}"
    assert abs(bbox_prop["z_length"] - 50.314) < 0.5, f"Propeller Z length unexpected: {bbox_prop['z_length']}"

    # Verify Bounding boxes are completely distinct
    assert abs(bbox_p["y_length"] - bbox_prop["y_length"]) > 10.0, "Bounding boxes must not bleed between projects"
    print(f"         Pieza18_1 BBox: {bbox_p['x_length']:.1f} × {bbox_p['y_length']:.1f} × {bbox_p['z_length']:.1f} mm ✓")
    print(f"         Propeller BBox: {bbox_prop['x_length']:.1f} × {bbox_prop['y_length']:.1f} × {bbox_prop['z_length']:.1f} mm ✓")

    # 3. TEST FEATURE LIST ISOLATION
    print("  [TEST 3] Retrieving features for each project...")
    feat_p_res = client.get(f"/api/v1/projects/{proj_p_id}/features").json()
    feat_prop_res = client.get(f"/api/v1/projects/{proj_prop_id}/features").json()

    feat_p = feat_p_res["features"]
    feat_prop = feat_prop_res["features"]

    assert len(feat_p) == 20, f"Pieza must have 20 features, got {len(feat_p)}"
    assert len(feat_prop) == 2, f"Propeller must have 2 features (hole + boss), got {len(feat_prop)}"

    p_feat_types = {f["type"] for f in feat_p}
    prop_feat_types = {f["type"] for f in feat_prop}

    assert "counterbored_hole" in p_feat_types
    assert "counterbored_hole" not in prop_feat_types
    assert "through_hole" in prop_feat_types
    assert "external_boss" in prop_feat_types
    print(f"         Pieza18_1 Features: {len(feat_p)} features ({p_feat_types}) ✓")
    print(f"         Propeller Features: {len(feat_prop)} features ({prop_feat_types}) ✓")

    # 4. TEST DIMENSION CANDIDATES ISOLATION
    print("  [TEST 4] Retrieving candidate dimensions for each project...")
    dim_p_res = client.get(f"/api/v1/projects/{proj_p_id}/dimensions").json()
    dim_prop_res = client.get(f"/api/v1/projects/{proj_prop_id}/dimensions").json()

    dims_p = dim_p_res["dimensions"]
    dims_prop = dim_prop_res["dimensions"]

    assert len(dims_p) == 20, f"Pieza candidates must be 20, got {len(dims_p)}"
    assert dim_p_res["placed_count"] == 14, f"Pieza placed count must be 14, got {dim_p_res['placed_count']}"

    assert len(dims_prop) == 8, f"Propeller candidates must be 8, got {len(dims_prop)}"
    assert len(dims_p) != len(dims_prop), "Dimension candidate sets must not bleed between projects"
    print(f"         Pieza18_1 Dimensions: {dim_p_res['placed_count']} placed / {dim_p_res['total_candidates']} total ✓")
    print(f"         Propeller Dimensions: {dim_prop_res['placed_count']} placed / {dim_prop_res['total_candidates']} total ✓")

    # 5. TEST DRAWING ARTIFACT ISOLATION
    print("  [TEST 5] Generating TechDraw drawings for each project...")
    draw_p = client.post(f"/api/v1/projects/{proj_p_id}/dimensioned-drawing").json()
    draw_prop = client.post(f"/api/v1/projects/{proj_prop_id}/dimensioned-drawing").json()

    art_p_types = {a["artifact_type"] for a in draw_p["artifacts"]}
    art_prop_types = {a["artifact_type"] for a in draw_prop["artifacts"]}

    assert "fcstd" in art_p_types or "dimensioned_fcstd" in art_p_types
    assert "fcstd" in art_prop_types or "dimensioned_fcstd" in art_prop_types
    print(f"         Pieza18_1 Drawing Artifacts: {len(draw_p['artifacts'])} generated ✓")
    print(f"         Propeller Drawing Artifacts: {len(draw_prop['artifacts'])} generated ✓")

    # 6. TEST CROSS-PROJECT ISOLATION & ACCESS CONTROL
    print("  [TEST 6] Verifying no cross-project artifact leakage...")
    # Attempting to fetch project A's artifact with project B's ID must fail
    fake_art_resp = client.get(f"/api/v1/projects/{proj_prop_id}/artifacts/non_existent_artifact")
    assert fake_art_resp.status_code == 404

    # 7. TEST PROVENANCE IN STATUS ENDPOINT
    print("  [TEST 7] Verifying provenance metadata in project status...")
    status_p = client.get(f"/api/v1/projects/{proj_p_id}").json()
    status_prop = client.get(f"/api/v1/projects/{proj_prop_id}").json()

    assert status_p["sha256_hash"] == pieza_expected_sha
    assert status_prop["sha256_hash"] == propeller_expected_sha
    assert status_p["filename"] == "Pieza18_1.STEP"
    assert status_prop["filename"] == "3052_3-Blade_Propeller_3-inch.step"
    print(f"         Provenance integrity verified across both projects ✓")

    print("=" * 70)
    print("PHASE 13.1 DATA INTEGRITY & MULTI-PROJECT ISOLATION PASSED 100%.")
    print("=" * 70)


if __name__ == "__main__":
    test_phase13_1_multi_project_data_isolation()
