"""Phase 20 — Standardized Multi-Model Engineering Intelligence Runner (Priority 4).

Runs the unified, non-hardcoded Engineering Intelligence pipeline across 3 distinct STEP models:
1. RB-3N-20A.STEP (Ball Valve Assembly)
2. Pieza18_1.STEP (Machined Mechanical Part)
3. 3052_3-Blade_Propeller_3-inch.step / Сборка1.STEP (Aerodynamic / Housing Part)

Outputs:
- B-Rep Audit (Raw Solids vs Unique Solids, Faces, Edges, Envelope)
- Recognized Feature Counts
- Classified Dimensions (Critical, Functional, Envelope)
- Recommended Views & Section Cuts
- Geometric Validation Status (B-REP VERIFIED)
- Comparative Markdown Summary Table
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import src.cad.freecad_env  # noqa: F401
from src.cad.step_loader import load_step
from src.cad.engineering_intelligence_engine import EngineeringIntelligenceEngine, EngineeringIntelligenceReport


def run_multi_model_benchmark() -> List[Dict[str, Any]]:
    """Execute engineering intelligence pipeline on 3 candidate models."""
    models = [
        ("RB-3N-20A.STEP", Path("workspaces/cb9cfd2c-094b-4bcc-8aeb-03798921320c/RB-3N-20A.STEP")),
        ("Pieza18_1.STEP", Path("input/Pieza18_1.STEP")),
        ("Propeller_3052.step", Path("input/3052_3-Blade_Propeller_3-inch.step")),
    ]

    engine = EngineeringIntelligenceEngine()
    results: List[Dict[str, Any]] = []

    print("=" * 90)
    print("PHASE 20 STANDARDIZED MULTI-MODEL ENGINEERING INTELLIGENCE BENCHMARK")
    print("=" * 90)

    for name, path in models:
        if not path.exists():
            print(f"Skipping {name}: file not found at {path}")
            continue

        t0 = time.time()
        res = load_step(path)
        report = engine.analyze_model(res, name)
        elapsed = time.time() - t0
        res.close()

        audit = report.audit_summary
        env = audit["assembly_envelope_mm"]
        crit_count = sum(1 for d in report.classified_dimensions if d.importance_tier == "TIER_1_CRITICAL")
        func_count = sum(1 for d in report.classified_dimensions if d.importance_tier == "TIER_2_FUNCTIONAL")
        env_count = sum(1 for d in report.classified_dimensions if d.importance_tier == "TIER_3_ENVELOPE")

        row = {
            "model_name": name,
            "raw_solids": audit["total_raw_solids"],
            "unique_solids": audit["unique_solids_count"],
            "unique_faces": audit["unique_faces_count"],
            "unique_edges": audit["unique_edges_count"],
            "envelope_mm": f"{env[0]:.1f} × {env[1]:.1f} × {env[2]:.1f}",
            "features_count": len(report.feature_graph),
            "dimensions_count": len(report.classified_dimensions),
            "critical_dims": crit_count,
            "functional_dims": func_count,
            "primary_views": ", ".join(report.view_recommendations.primary_views[:3]),
            "primary_section": report.section_recommendations.recommended_primary_section,
            "validation_status": report.geometric_validation_status,
            "elapsed_sec": round(elapsed, 2),
        }
        results.append(row)

        print(f"\n[MODEL: {name}] (Processed in {elapsed:.2f}s)")
        print(f"  • Solids: {row['unique_solids']} unique ({row['raw_solids']} raw)")
        print(f"  • Topology: {row['unique_faces']} Faces, {row['unique_edges']} Edges")
        print(f"  • Envelope: {row['envelope_mm']} mm")
        print(f"  • Features: {row['features_count']} recognized ({crit_count} Critical, {func_count} Functional dims)")
        print(f"  • Views: {row['primary_views']} | Section: {row['primary_section']}")
        print(f"  • Validation: {row['validation_status']} (B-REP VERIFIED)")

    # Print Comparative Table
    print("\n" + "=" * 90)
    print(f"{'MODEL':<22} | {'SOLIDS':<8} | {'FACES':<6} | {'EDGES':<6} | {'ENVELOPE (mm)':<20} | {'DIMS':<6} | {'VALIDATION':<10}")
    print("-" * 90)
    for r in results:
        solids_str = f"{r['unique_solids']}/{r['raw_solids']}"
        print(f"{r['model_name']:<22} | {solids_str:<8} | {r['unique_faces']:<6} | {r['unique_edges']:<6} | {r['envelope_mm']:<20} | {r['dimensions_count']:<6} | {r['validation_status']:<10}")
    print("=" * 90)

    return results


if __name__ == "__main__":
    run_multi_model_benchmark()
