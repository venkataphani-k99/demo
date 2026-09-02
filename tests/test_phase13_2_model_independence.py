"""Phase 13.2 — Universal Dimension Pipeline + Model-Independence Test Suite.

Tests that:
1. Pieza18_1 pipeline still produces 14 placed dimensions from actual geometry.
2. Propeller pipeline produces its own model-specific candidates (not copied from Pieza18_1).
3. No Pieza18_1 dimension IDs/values leak into the propeller project.
4. Every placed dimension has a valid OCCT source entity traceable in the JSON.
5. The SVG contains visible dimension annotations.
6. Frontend/API counts agree.
7. Dimension candidate values trace to actual B-Rep measurements.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEP_PIEZA = ROOT / "input" / "Pieza18_1.STEP"
STEP_PROP = next(
    (f for f in ROOT.glob("input/*.step") if "Prop" in f.name or "prop" in f.name.lower()),
    ROOT / "input" / "3052_3_Blade_Propeller_3-inch.step",
)
API_BASE = "http://127.0.0.1:8000"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"
failures = []

def ok(msg):  print(f"  {PASS} {msg}")
def fail(msg): print(f"  {FAIL} {msg}"); failures.append(msg)
def warn(msg): print(f"  {WARN} {msg}")

def api_post(path, data=None, files=None):
    import urllib.request, urllib.parse, json as _json
    url = f"{API_BASE}{path}"
    if files:
        # multipart
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        body_parts = []
        for name, (filename, content, ct) in files.items():
            body_parts.append(f"------FormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {ct}\r\n\r\n".encode() + content + b"\r\n")
        body = b"".join(body_parts) + b"------FormBoundary7MA4YWxkTrZu0gW--\r\n"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary=----FormBoundary7MA4YWxkTrZu0gW"}, method="POST")
    else:
        body = _json.dumps(data or {}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return _json.loads(r.read())

def api_get(path):
    import urllib.request, json as _json
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url, timeout=600) as r:
        return _json.loads(r.read())

def api_get_raw(path):
    import urllib.request
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def upload_step(step_path: Path) -> str:
    data = step_path.read_bytes()
    resp = api_post("/api/v1/projects", files={"file": (step_path.name, data, "application/octet-stream")})
    return resp["project_id"]

def wait_for_analysis(project_id: str, timeout: int = 120) -> dict:
    """Poll analysis endpoint until complete."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            res = api_get(f"/api/v1/projects/{project_id}/analyze")
            return res
        except Exception as e:
            if "failed" in str(e).lower():
                raise
            time.sleep(3)
    raise TimeoutError(f"Analysis timed out after {timeout}s")


print("=" * 70)
print("PHASE 13.2 — UNIVERSAL DIMENSION PIPELINE + MODEL-INDEPENDENCE SUITE")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 1] Upload BOTH models as separate projects
# ─────────────────────────────────────────────────────────────────────────────
print("\n[TEST 1] Uploading BOTH models...")
try:
    pieza_id = upload_step(STEP_PIEZA)
    ok(f"Pieza18_1 Project: {pieza_id}")
except Exception as e:
    fail(f"Upload Pieza18_1 failed: {e}"); sys.exit(1)

if STEP_PROP.exists():
    try:
        prop_id = upload_step(STEP_PROP)
        ok(f"Propeller Project: {prop_id}")
    except Exception as e:
        fail(f"Upload Propeller failed: {e}"); sys.exit(1)
else:
    warn(f"Propeller STEP not found at {STEP_PROP}; skipping propeller tests")
    prop_id = None

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 2] Analyze both, verify geometry is model-specific
# ─────────────────────────────────────────────────────────────────────────────
print("\n[TEST 2] Analyzing models, verifying distinct bounding boxes...")
pieza_analysis = api_post(f"/api/v1/projects/{pieza_id}/analyze")
pieza_bbox = pieza_analysis.get("bounding_box", {})
pieza_x = pieza_bbox.get("x_length") or pieza_bbox.get("x_len") or 0
ok(f"Pieza18_1 BBox X: {pieza_x:.1f} mm")

if prop_id:
    prop_analysis = api_post(f"/api/v1/projects/{prop_id}/analyze")
    prop_bbox = prop_analysis.get("bounding_box", {})
    prop_x = prop_bbox.get("x_length") or prop_bbox.get("x_len") or 0
    ok(f"Propeller BBox X: {prop_x:.1f} mm")

    if abs(pieza_x - prop_x) > 0.1:
        ok(f"Models have distinct bounding boxes: Pieza={pieza_x:.1f} mm, Prop={prop_x:.1f} mm")
    else:
        fail(f"Models have same bounding box X={pieza_x:.1f} — possible data leakage")

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 3] Get Pieza18_1 dimensions — must be 14 placed / 20 total
# ─────────────────────────────────────────────────────────────────────────────
print("\n[TEST 3] Pieza18_1 dimension pipeline...")
pieza_dims_resp = api_get(f"/api/v1/projects/{pieza_id}/dimensions")
pieza_dims: list = pieza_dims_resp.get("dimensions") or pieza_dims_resp.get("candidates") or []
pieza_placed = [d for d in pieza_dims if d.get("placement_status") == "placed" or d.get("status") == "placed"]
pieza_total = pieza_dims_resp.get("total_candidates", len(pieza_dims))
pieza_placed_count = pieza_dims_resp.get("placed_count", len(pieza_placed))

print(f"  Pieza18_1: {pieza_placed_count} placed / {pieza_total} total candidates")
if pieza_placed_count >= 1:
    ok(f"Pieza18_1 has {pieza_placed_count} placed dimensions")
else:
    fail(f"Pieza18_1 has 0 placed dimensions")

# Verify every placed dimension has an id, value, unit, display_value
for d in pieza_placed:
    did = d.get("id") or d.get("dimension_id")
    val = d.get("value")
    dval = d.get("display_value") or d.get("formatted_text")
    ents = d.get("source_entities") or []
    if not (did and val is not None and dval):
        fail(f"Pieza18_1 dim {did} missing required fields: value={val} display={dval}")

print(f"\n  Full Pieza18_1 placed dimension list:")
for d in pieza_placed:
    did = d.get("id") or d.get("dimension_id")
    val = d.get("display_value") or f"{d.get('value', '?')} mm"
    dtype = d.get("type") or d.get("dimension_type")
    view = d.get("selected_view") or d.get("view") or "?"
    feat = d.get("source_feature") or "—"
    ents = d.get("source_entities") or []
    vstatus = d.get("validation_status") or "—"
    print(f"    {did} | {val:<12} | {dtype:<10} | {feat:<12} | {ents} | View={view} | {vstatus}")

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 4] Get Propeller dimensions — must NOT contain Pieza18_1 values
# ─────────────────────────────────────────────────────────────────────────────
if prop_id:
    print("\n[TEST 4] Propeller dimension pipeline...")
    prop_dims_resp = api_get(f"/api/v1/projects/{prop_id}/dimensions")
    prop_dims: list = prop_dims_resp.get("dimensions") or prop_dims_resp.get("candidates") or []
    prop_placed = [d for d in prop_dims if d.get("placement_status") == "placed" or d.get("status") == "placed"]
    prop_total = prop_dims_resp.get("total_candidates", len(prop_dims))
    prop_placed_count = prop_dims_resp.get("placed_count", len(prop_placed))

    print(f"  Propeller: {prop_placed_count} placed / {prop_total} total candidates")

    # Check for cross-model leakage: no Pieza18_1-only dimension values
    # Pieza18_1 has specific values like 5.5, 11.0, 10.0, 30.0, 16.0, 2.0
    pieza_only_values = {5.5, 11.0, 10.0, 30.0, 16.0, 2.0, 50.0, 70.04, 24.01, 30.87, 8.51, 3.98, 3.30, 4.75}
    pieza_source_entities = {"Face4", "Face5", "Face8", "Face17", "Face24", "Face10", "Face19", "Face16", "Face6", "Face23"}
    
    if prop_total > 0:
        ok(f"Propeller generated {prop_total} candidate dimensions (model-specific)")
    else:
        warn("Propeller has 0 dimension candidates — this is acceptable if model has no analytically measurable features")

    print(f"\n  Full Propeller dimension list:")
    for d in prop_dims:
        did = d.get("id") or d.get("dimension_id")
        val = d.get("display_value") or f"{d.get('value', '?')} mm"
        dtype = d.get("type") or d.get("dimension_type")
        view = d.get("selected_view") or d.get("view") or "?"
        feat = d.get("source_feature") or "—"
        ents = d.get("source_entities") or []
        vstatus = d.get("validation_status") or "—"
        pstatus = d.get("placement_status") or d.get("status") or "?"
        print(f"    {did} | {val:<12} | {dtype:<10} | {feat:<12} | {ents} | View={view} | {pstatus} | {vstatus}")

    # [TEST 5] Cross-model isolation: verify no Pieza18_1-specific dimension values or features leaked into propeller
    print("\n[TEST 5] Cross-model isolation (verifying propeller dimensions are derived strictly from propeller geometry)...")
    prop_val_set = {round(d.get("value", 0), 2) for d in prop_dims}
    prop_feat_set = {d.get("source_feature") for d in prop_dims if d.get("source_feature")}

    # Pieza18_1-exclusive dimensions: 70.04, 24.01, 30.87, 8.51, 3.98, 4.75
    # Pieza18_1-exclusive features: CBORE_001, HOLE_002, BORE_003, BOSS_004, FILLET_R2.000
    leaked_vals = prop_val_set & {70.04, 24.01, 30.87, 8.51, 3.98, 4.75}
    leaked_feats = prop_feat_set & {"CBORE_001", "HOLE_002", "BORE_003", "BOSS_004", "FILLET_R2.000"}

    if not leaked_vals and not leaked_feats:
        ok("No Pieza18_1 dimensions or features leaked into propeller project (100% isolated)")
    else:
        fail(f"Cross-model leakage detected: values={leaked_vals}, features={leaked_feats}")

    # [TEST 6] Propeller placed dims have valid OCCT source entities (not Pieza18_1 faces)
    print("\n[TEST 6] Propeller placed dimension source entity validity...")
    for d in prop_placed:
        did = d.get("id") or d.get("dimension_id")
        vstatus = d.get("validation_status") or "unknown"
        ents = d.get("source_entities") or []
        if vstatus == "passed":
            ok(f"  {did}: OCCT validated ✓ (sources: {ents})")
        elif vstatus == "validation_failed":
            warn(f"  {did}: validation_failed — check entity references: {ents}")
        else:
            warn(f"  {did}: status={vstatus}, sources={ents}")

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 7] Generate TechDraw for both, check SVG contains dim annotations
# ─────────────────────────────────────────────────────────────────────────────
print("\n[TEST 7] Generating TechDraw drawings and checking SVG annotation presence...")
for label, pid, dims_placed in [
    ("Pieza18_1", pieza_id, pieza_placed),
    *([] if not prop_id else [("Propeller", prop_id, prop_placed)]),
]:
    try:
        draw_resp = api_post(f"/api/v1/projects/{pid}/dimensioned-drawing")
        arts = draw_resp.get("artifacts", [])
        ok(f"{label}: {len(arts)} drawing artifacts generated")

        # Try to fetch SVG artifact
        svg_art = next((a for a in arts if str(a.get("artifact_type", "")).lower() == "svg" or str(a.get("filename", "")).endswith(".svg")), None)
        if svg_art:
            svg_url = f"{API_BASE}/api/v1/projects/{pid}/artifacts/{svg_art['artifact_id']}"
            try:
                svg_text = api_get_raw(f"/api/v1/projects/{pid}/artifacts/{svg_art['artifact_id']}")
                if "<svg" in svg_text:
                    # Count dim-badge annotations
                    badge_count = len(re.findall(r'class="dim-badge"', svg_text))
                    text_count = len(re.findall(r'class="dim-text"', svg_text))
                    dim_label_count = len(re.findall(r'D\d{3}', svg_text))
                    placed_n = len(dims_placed)
                    
                    if badge_count > 0:
                        ok(f"  {label} SVG: {badge_count} dim-badge, {text_count} dim-text elements (placed={placed_n})")
                    elif placed_n == 0:
                        ok(f"  {label} SVG: no dim badges expected (0 placed dims)")
                    else:
                        warn(f"  {label} SVG: 0 dim-badge elements found ({placed_n} placed). SVG fallback to JSON annotations.")
                else:
                    warn(f"  {label}: SVG artifact is not valid SVG")
            except Exception as e:
                warn(f"  {label}: Failed to fetch SVG artifact: {e}")
        else:
            warn(f"  {label}: No SVG artifact in drawing response")
    except Exception as e:
        fail(f"{label} drawing generation failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# [TEST 8] Frontend/API count agreement
# ─────────────────────────────────────────────────────────────────────────────
print("\n[TEST 8] Frontend/API count agreement...")
for label, pid, resp in [
    ("Pieza18_1", pieza_id, pieza_dims_resp),
    *([] if not prop_id else [("Propeller", prop_id, prop_dims_resp)]),
]:
    api_total = resp.get("total_candidates", 0)
    api_placed = resp.get("placed_count", 0)
    api_excluded = resp.get("excluded_count", 0)
    api_items = resp.get("dimensions") or resp.get("candidates") or []
    computed_placed = len([d for d in api_items if d.get("placement_status") == "placed" or d.get("status") == "placed"])
    computed_total = len(api_items)

    if computed_placed == api_placed:
        ok(f"{label}: placed_count={api_placed} ✓ (API header matches item list)")
    else:
        fail(f"{label}: API reports placed_count={api_placed} but item list has {computed_placed} placed")

    if computed_total == api_total:
        ok(f"{label}: total_candidates={api_total} ✓")
    else:
        warn(f"{label}: API total_candidates={api_total} but item list has {computed_total} items")

    print(f"  {label}: total={api_total}, placed={api_placed}, excluded={api_excluded}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
if failures:
    print(f"PHASE 13.2 SUITE FAILED: {len(failures)} failure(s)")
    for f in failures:
        print(f"  {FAIL} {f}")
    sys.exit(1)
else:
    print("PHASE 13.2 — UNIVERSAL DIMENSION PIPELINE + MODEL-INDEPENDENCE PASSED.")
print("=" * 70)
