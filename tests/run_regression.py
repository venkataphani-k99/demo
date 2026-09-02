"""Full regression suite runner for Phase 1-7."""
import subprocess, sys
from pathlib import Path

PYTHON = r"C:\Program Files\FreeCAD 1.1\bin\python.exe"
TESTS = [
    r"tests\test_phase1_box.py",
    r"tests\test_phase2_step_import.py",
    r"tests\test_phase3_deep_geometry.py",
    r"tests\test_phase4_measurements.py",
    r"tests\test_phase5_feature_recognition.py",
    r"tests\test_phase6_techdraw.py",
    r"tests\test_phase7_dimensions.py",
    r"tests\test_phase8_dimension_placement.py",
    r"tests\test_phase9a_complete_dimensioning.py",
    r"tests\test_phase10_engineering_intelligence.py",
    r"tests\test_phase11_live_ai.py",
    r"tests\test_phase11_multimodal_audit.py",
    r"tests\test_phase11_6_visual_review.py",
    r"tests\test_phase12_engineering_issues.py",
]

ROOT = Path(__file__).resolve().parent.parent
failed = []
for t in TESTS:
    print(f"\n{'='*60}\nRunning: {t}\n{'='*60}")
    r = subprocess.run([PYTHON, t], cwd=str(ROOT))
    if r.returncode != 0:
        failed.append(t)
        print(f"FAILED: {t}")

print(f"\n{'='*60}")
if failed:
    print(f"REGRESSION FAILED: {len(failed)} suite(s) failed:")
    for f in failed:
        print(f"  {f}")
    sys.exit(1)
else:
    print(f"ALL {len(TESTS)} REGRESSION SUITES PASSED")
    sys.exit(0)
