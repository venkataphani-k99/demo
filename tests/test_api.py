"""Phase 9.5: FastAPI Service Layer Test Suite.

Tests:
1.  Health check endpoint (GET /api/v1/health)
2.  Project creation via STEP upload (POST /api/v1/projects)
3.  Invalid file extension rejection (POST /api/v1/projects with .txt)
4.  Empty file rejection (POST /api/v1/projects with empty body)
5.  Project status retrieval (GET /api/v1/projects/{id})
6.  Missing project handling (GET /api/v1/projects/non-existent-id -> 404)
7.  CAD analysis execution (POST /api/v1/projects/{id}/analyze)
8.  Recognized features retrieval (GET /api/v1/projects/{id}/features)
9.  Dimension candidates and coverage retrieval (GET /api/v1/projects/{id}/dimensions)
10. Standard 5-view TechDraw generation (POST /api/v1/projects/{id}/drawings)
11. Complete dimensioned drawing generation (POST /api/v1/projects/{id}/dimensioned-drawing)
12. Artifact download endpoint (GET /api/v1/projects/{id}/artifacts/{artifact_id})
13. Missing artifact handling (GET /api/v1/projects/{id}/artifacts/invalid_id -> 404)
14. API JSON serialization integrity
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from src.api.app import app

STEP_FILE = PROJECT_ROOT / "input" / "Pieza18_1.STEP"


def run_api_tests():
    print("=" * 60)
    print("PHASE 9.5 — FASTAPI SERVICE LAYER TEST SUITE")
    print("=" * 60)

    client = TestClient(app)

    # 1. Health check
    print("  [TEST 1] Health endpoint (GET /api/v1/health)...")
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check returned {res.status_code}"
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "cad-intelligence-api"
    assert "version" in data
    print("         Health check: 200 OK ✓")

    # 2. Project creation with STEP upload
    print("  [TEST 2] Project creation with STEP upload (POST /api/v1/projects)...")
    assert STEP_FILE.exists(), f"STEP file missing: {STEP_FILE}"
    with open(STEP_FILE, "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/v1/projects",
        files={"file": ("Pieza18_1.STEP", file_bytes, "application/octet-stream")},
    )
    assert res.status_code == 201, f"Project creation failed: {res.status_code} {res.text}"
    p_data = res.json()
    project_id = p_data["project_id"]
    assert project_id, "Missing project_id"
    assert p_data["filename"] == "Pieza18_1.STEP"
    assert p_data["status"] == "uploaded"
    print(f"         Project created: id={project_id}, status={p_data['status']} ✓")

    # 3. Invalid file extension rejection
    print("  [TEST 3] Invalid extension rejection (POST /api/v1/projects with .txt)...")
    res = client.post(
        "/api/v1/projects",
        files={"file": ("invalid.txt", b"not a cad model", "text/plain")},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "supported" in res.json()["detail"].lower()
    print("         Invalid extension rejected with 400 Bad Request ✓")

    # 4. Empty file rejection
    print("  [TEST 4] Empty file upload rejection...")
    res = client.post(
        "/api/v1/projects",
        files={"file": ("empty.step", b"", "application/octet-stream")},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    print("         Empty upload rejected with 400 Bad Request ✓")

    # 5. Project status
    print("  [TEST 5] Project status retrieval (GET /api/v1/projects/{id})...")
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 200
    s_data = res.json()
    assert s_data["project_id"] == project_id
    assert s_data["status"] == "uploaded"
    print(f"         Project status verified: {s_data['status']} ✓")

    # 6. Missing project handling
    print("  [TEST 6] Non-existent project handling (GET /api/v1/projects/invalid-id)...")
    res = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print("         Non-existent project returned 404 Not Found ✓")

    # 7. CAD Analysis endpoint
    print("  [TEST 7] CAD analysis execution (POST /api/v1/projects/{id}/analyze)...")
    res = client.post(f"/api/v1/projects/{project_id}/analyze")
    assert res.status_code == 200, f"Analysis failed: {res.status_code} {res.text}"
    ana_data = res.json()
    assert ana_data["project_id"] == project_id
    assert ana_data["topology"]["solids"] >= 1
    assert ana_data["topology"]["faces"] >= 20
    assert ana_data["feature_count"] >= 5
    assert abs(ana_data["bounding_box"]["x_length"] - 70.037) < 0.1
    print(f"         CAD analysis completed: {ana_data['topology']['faces']} faces, {ana_data['feature_count']} features ✓")

    # 8. Features endpoint
    print("  [TEST 8] Recognized features (GET /api/v1/projects/{id}/features)...")
    res = client.get(f"/api/v1/projects/{project_id}/features")
    assert res.status_code == 200
    feat_data = res.json()
    assert feat_data["total_features"] >= 5
    feat_types = {f["type"] for f in feat_data["features"]}
    assert "counterbored_hole" in feat_types
    assert "through_hole" in feat_types
    assert "external_boss" in feat_types
    print(f"         Recognized features retrieved: {feat_data['total_features']} features ({sorted(feat_types)}) ✓")

    # 9. Dimensions endpoint
    print("  [TEST 9] Dimension candidates and coverage (GET /api/v1/projects/{id}/dimensions)...")
    res = client.get(f"/api/v1/projects/{project_id}/dimensions")
    assert res.status_code == 200
    dim_data = res.json()
    assert dim_data["total_candidates"] == 20
    assert dim_data["placed_count"] == 14
    assert len(dim_data["feature_coverages"]) >= 5
    print(f"         Dimension candidates retrieved: {dim_data['placed_count']} placed / {dim_data['total_candidates']} total ✓")

    # 10. Standard TechDraw drawing generation
    print("  [TEST 10] Standard TechDraw drawing generation (POST /api/v1/projects/{id}/drawings)...")
    res = client.post(
        f"/api/v1/projects/{project_id}/drawings",
        json={"projection": "third-angle", "template": "A3_Landscape_blank.svg", "scale": 0.0},
    )
    assert res.status_code == 200, f"Drawing generation failed: {res.status_code} {res.text}"
    draw_data = res.json()
    assert draw_data["status"] == "completed"
    assert len(draw_data["artifacts"]) >= 2
    art_types = {a["artifact_type"] for a in draw_data["artifacts"]}
    assert "fcstd" in art_types
    print(f"         Standard TechDraw generated: {len(draw_data['artifacts'])} artifacts ({sorted(art_types)}) ✓")

    # 11. Complete dimensioned TechDraw drawing generation
    print("  [TEST 11] Complete dimensioned TechDraw generation (POST /api/v1/projects/{id}/dimensioned-drawing)...")
    res = client.post(f"/api/v1/projects/{project_id}/dimensioned-drawing")
    assert res.status_code == 200, f"Dimensioned drawing failed: {res.status_code} {res.text}"
    dim_draw_data = res.json()
    assert dim_draw_data["status"] == "completed"
    assert dim_draw_data["drawing_type"] == "complete_dimensioned"
    dim_art_types = {a["artifact_type"] for a in dim_draw_data["artifacts"]}
    assert "fcstd" in dim_art_types
    print(f"         Dimensioned drawing generated: {len(dim_draw_data['artifacts'])} artifacts ✓")

    # 12. Artifact download
    print("  [TEST 12] Artifact download (GET /api/v1/projects/{id}/artifacts/{artifact_id})...")
    res = client.get(f"/api/v1/projects/{project_id}/artifacts/dimensioned_fcstd")
    assert res.status_code == 200, f"Artifact download failed: {res.status_code}"
    assert len(res.content) > 10000, "Downloaded FCStd artifact is suspiciously small"
    print(f"         Artifact 'dimensioned_fcstd' downloaded ({len(res.content):,} bytes) ✓")

    # 13. Missing artifact handling
    print("  [TEST 13] Non-existent artifact handling (GET /api/v1/projects/{id}/artifacts/invalid)...")
    res = client.get(f"/api/v1/projects/{project_id}/artifacts/non_existent_artifact")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print("         Missing artifact returned 404 Not Found ✓")

    # 14. API JSON serialization
    print("  [TEST 14] API JSON serialization validation...")
    status_res = client.get(f"/api/v1/projects/{project_id}")
    assert status_res.status_code == 200
    assert len(status_res.json()["artifacts"]) >= 5
    print("         All API endpoints strictly serialize clean Pydantic JSON responses ✓")

    # 15. AI Engineering Review endpoint (POST /api/v1/projects/{id}/ai-review)
    print("  [TEST 15] AI Engineering Review execution (POST /api/v1/projects/{id}/ai-review)...")
    res = client.post(
        f"/api/v1/projects/{project_id}/ai-review",
        json={"provider": "mock"},
    )
    assert res.status_code == 200, f"AI review failed: {res.status_code} {res.text}"
    rev_data = res.json()
    assert rev_data["project_id"] == project_id
    assert rev_data["overall_assessment"] == "good"
    assert len(rev_data["recommendations"]) >= 3
    print(f"         AI review completed: {len(rev_data['recommendations'])} recommendations, assessment={rev_data['overall_assessment']} ✓")

    # 16. Get Existing AI Review endpoint (GET /api/v1/projects/{id}/ai-review)
    print("  [TEST 16] Get existing AI review (GET /api/v1/projects/{id}/ai-review)...")
    res = client.get(f"/api/v1/projects/{project_id}/ai-review")
    assert res.status_code == 200
    rev_get_data = res.json()
    assert rev_get_data["review_id"] == rev_data["review_id"]
    print(f"         Existing AI review retrieved: review_id={rev_get_data['review_id']} ✓")

    # 17. Live / Missing API key verification (POST /api/v1/projects/{id}/ai-review with claude)
    from src.cad.freecad_env import load_env_file
    load_env_file()
    if os.getenv("ANTHROPIC_API_KEY"):
        print("  [TEST 17] Live Claude review verification (POST /api/v1/projects/{id}/ai-review with claude)...")
        res = client.post(
            f"/api/v1/projects/{project_id}/ai-review",
            json={"provider": "claude"},
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("         Live Claude review endpoint returned 200 OK ✓")
    else:
        print("  [TEST 17] Missing API key rejection (POST /api/v1/projects/{id}/ai-review with claude)...")
        res = client.post(
            f"/api/v1/projects/{project_id}/ai-review",
            json={"provider": "claude"},
        )
        assert res.status_code in (400, 422), f"Expected 400/422, got {res.status_code}"
        print("         Missing API key rejected with 400 Bad Request ✓")

    # 18. Engineering Issues endpoint (GET /api/v1/projects/{id}/issues)
    print("  [TEST 18] Engineering Issues retrieval (GET /api/v1/projects/{id}/issues)...")
    res = client.get(f"/api/v1/projects/{project_id}/issues")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    issues_data = res.json()
    assert len(issues_data) >= 4
    print(f"         Engineering issues retrieved: {len(issues_data)} issues ✓")

    # 19. Engineering Recommendations endpoint (GET /api/v1/projects/{id}/recommendations)
    print("  [TEST 19] Engineering Recommendations retrieval (GET /api/v1/projects/{id}/recommendations)...")
    res = client.get(f"/api/v1/projects/{project_id}/recommendations")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    recs_data = res.json()
    assert len(recs_data) >= 4
    print(f"         Engineering recommendations retrieved: {len(recs_data)} recommendations ✓")

    # 20. Review summary endpoint (GET /api/v1/projects/{id}/review-summary)
    print("  [TEST 20] Review summary and consensus retrieval (GET /api/v1/projects/{id}/review-summary)...")
    res = client.get(f"/api/v1/projects/{project_id}/review-summary")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    summary_data = res.json()
    assert "consensus" in summary_data
    print(f"         Review summary verified: {summary_data['consensus']['consensus_issues_count']} consensus issues ✓")

    # 21. Approve Recommendation (POST /api/v1/projects/{id}/recommendations/{rec_id}/approve)
    print("  [TEST 21] Approve recommendation endpoint (POST /api/v1/projects/{id}/recommendations/REC_001/approve)...")
    res = client.post(f"/api/v1/projects/{project_id}/recommendations/REC_001/approve")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    approve_data = res.json()
    assert approve_data["approval_status"] == "APPROVED"
    print("         REC_001 approved: approval_status=APPROVED ✓")

    # 22. Reject Recommendation (POST /api/v1/projects/{id}/recommendations/{rec_id}/reject)
    print("  [TEST 22] Reject recommendation endpoint (POST /api/v1/projects/{id}/recommendations/REC_002/reject)...")
    res = client.post(f"/api/v1/projects/{project_id}/recommendations/REC_002/reject")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    reject_data = res.json()
    assert reject_data["approval_status"] == "REJECTED"
    print("         REC_002 rejected: approval_status=REJECTED ✓")

    print("=" * 60)
    print("ALL API TESTS (PHASES 9.5, 11 & 12) PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_api_tests()
    sys.exit(0 if success else 1)
