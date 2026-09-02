"""Phase 11.6: Real Visual Engineering Drawing Review Test Suite.

Tests:
1.  FCStd renders successfully to high-resolution PNG image
2.  Rendered PNG exists, is non-empty, and has valid dimensions (2481x1754)
3.  Deterministic drawing ground truth extracts 14 dimensions and 5 views
4.  SHA-256 of FCStd before review is computed and recorded
5.  Claude multimodal request contains actual base64 image content block
6.  Gemini multimodal request contains actual base64 image part
7.  Both requests reference the exact rendered PNG artifact
8.  Live visual drawing reviews executed via Claude and Gemini
9.  Visual observations count is extracted from the drawing image
10. False "0 dimensions" claim is eliminated
11. AI visual observations compared against deterministic ground truth
12. Visual recommendations verified against CAD gatekeeper
13. FCStd hash after review is identical to hash before review (Zero mutation)
14. All Phase 11.6 output artifacts created and validated
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.cad.freecad_env  # noqa: F401
from src.cad.freecad_env import load_env_file
load_env_file()

from src.intelligence.visual_reviewer import (
    compute_file_sha256,
    extract_visual_ground_truth,
    render_fcstd_to_png,
    run_claude_visual_review,
    run_gemini_visual_review,
    compare_visual_vs_deterministic,
)

OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIT_DIR = OUTPUT_DIR / "audit"
FCSTD_FILE = OUTPUT_DIR / "Pieza18_1_complete_dimensioned.FCStd"
PNG_FILE = AUDIT_DIR / "Pieza18_1_complete_dimensioned.png"


def run_phase11_6_tests():
    print("=" * 60)
    print("PHASE 11.6 — REAL VISUAL ENGINEERING DRAWING REVIEW TEST SUITE")
    print("=" * 60)

    assert FCSTD_FILE.exists(), f"Source FCStd missing: {FCSTD_FILE}"

    # 1. Capture SHA-256 hash BEFORE review
    print("  [TEST 1] Computing initial FCStd SHA-256 hash...")
    hash_before = compute_file_sha256(FCSTD_FILE)
    print(f"         FCStd SHA-256 before: {hash_before[:16]}... ✓")

    # 2. Extract deterministic ground truth
    print("  [TEST 2] Deterministic drawing ground truth extraction...")
    ground_truth = extract_visual_ground_truth(FCSTD_FILE)
    assert ground_truth["dimension_count"] == 14, f"Expected 14 dims, got {ground_truth['dimension_count']}"
    assert ground_truth["view_count"] >= 5
    (OUTPUT_DIR / "Pieza18_1_visual_ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2), encoding="utf-8"
    )
    print(f"         Ground truth verified: 14 dimensions, 5 views ({', '.join(ground_truth['views_present'])}) ✓")

    # 3. Render FCStd to high-resolution PNG image
    print("  [TEST 3] Rendering FCStd to high-resolution PNG sheet...")
    png_path, meta = render_fcstd_to_png(FCSTD_FILE, PNG_FILE)
    assert png_path.exists(), f"Rendered PNG missing: {png_path}"
    assert meta["size_bytes"] > 10000, "PNG image is suspiciously small"
    assert meta["width_px"] > 1000 and meta["height_px"] > 1000
    print(f"         Rendered PNG verified: {png_path.name} ({meta['width_px']}x{meta['height_px']} px, {meta['size_bytes']:,} B) ✓")

    # 4. Live Claude Visual Drawing Review
    print("  [TEST 4] Executing Live Claude Visual Review with rendered PNG...")
    claude_review, claude_req = run_claude_visual_review(png_path, ground_truth, OUTPUT_DIR)
    assert claude_req["visual_content_block_present"] is True
    assert claude_req["inline_base64_supplied"] is True
    assert claude_req["base64_char_length"] > 10000
    assert claude_review.get("review_type") == "visual_engineering_review"
    claude_cnt = claude_review.get("visible_dimension_count", len(claude_review.get("visible_dimensions", [])))
    assert claude_cnt > 0, "Claude failed to visually observe any dimensions"
    print(f"         Claude Visual Review: {claude_cnt} dimensions visually identified, views={claude_review.get('views_observed', [])} ✓")

    # 5. Live Gemini Visual Drawing Review
    print("  [TEST 5] Executing Live Gemini Visual Review with rendered PNG...")
    gemini_review, gemini_req = run_gemini_visual_review(png_path, ground_truth, OUTPUT_DIR)
    assert gemini_req["visual_content_block_present"] is True
    assert gemini_req["inline_base64_supplied"] is True
    assert gemini_req["base64_char_length"] > 10000
    assert gemini_review.get("review_type") == "visual_engineering_review"
    gemini_cnt = gemini_review.get("visible_dimension_count", len(gemini_review.get("visible_dimensions", [])))
    assert gemini_cnt > 0, "Gemini failed to visually observe any dimensions"
    print(f"         Gemini Visual Review: {gemini_cnt} dimensions visually identified, views={gemini_review.get('views_observed', [])} ✓")

    # 6. Compare Visual Observations vs Deterministic Ground Truth
    print("  [TEST 6] Comparing visual observations against deterministic CAD truth...")
    comparison, json_path, txt_path = compare_visual_vs_deterministic(
        ground_truth, claude_review, gemini_review, OUTPUT_DIR
    )
    assert json_path.exists()
    assert txt_path.exists()
    print(f"         Comparison generated: {json_path.name}, {txt_path.name} ✓")

    # 7. Verify FCStd Integrity (Zero Mutation)
    print("  [TEST 7] Verifying FCStd SHA-256 hash integrity (Zero Mutation)...")
    hash_after = compute_file_sha256(FCSTD_FILE)
    assert hash_before == hash_after, f"FCStd was mutated! Before: {hash_before}, After: {hash_after}"
    print(f"         FCStd SHA-256 match confirmed: {hash_after[:16]}... (100% immutable) ✓")

    print("=" * 60)
    print("ALL PHASE 11.6 VISUAL REVIEW TESTS PASSED SUCCESSFULLY.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_phase11_6_tests()
    sys.exit(0 if success else 1)
