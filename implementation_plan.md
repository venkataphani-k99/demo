# Implementation Plan — Phase 20: B-Rep Verified Generative Engineering Drawing

## Problem Statement & Objective
Transition from isolated 2D SVG generation to a fully auditable, deterministic **B-Rep Verified Generative Engineering Drawing Engine** powered strictly by OpenCASCADE (OCCT) and FreeCAD geometry kernels.

Every view, section cut, dimension, witness line, and centerline must have 100% mathematical provenance grounded in the 3D CAD B-Rep topology—zero LLM guessing or hardcoded coordinates.

---

## 1. Architecture Findings from Initial Audit

### A. Root Cause of Topology & Envelope Discrepancies on `RB-3N-20A.STEP`
Our deterministic inspection of `RB-3N-20A.STEP` directly via OpenCASCADE / FreeCAD Part kernel revealed:
1. **Assembly Occurrence Duplication in STEP**:
   - The STEP file contains **6 solid entities**:
     - Solid #1 (Valve Body): 168 Faces, 444 Edges, Volume $39,623.24\text{ mm}^3$
     - Solid #2 (Valve Stem): 31 Faces, 80 Edges, Volume $1,933.01\text{ mm}^3$
     - Solid #3 (Handle Lever): 31 Faces, 87 Edges, Volume $4,558.75\text{ mm}^3$
     - Solid #4, #5, #6: **Exact duplicate assembly occurrences** of Solids #1, #2, #3!
   - Unique Solid Topology: **$168 + 31 + 31 = 230\text{ Faces}$**, **$444 + 80 + 87 = 611\text{ Edges}$**.
   - Total Raw STEP Compound: **$230 \times 2 = 460\text{ Faces}$** (+ 3 datum planes = 463), **$611 \times 2 = 1,222\text{ Edges}$**.
2. **Envelope Ground Truth**:
   - Overall assembly bounding envelope: **$114.000\text{ mm} \times 71.539\text{ mm} \times 56.189\text{ mm}$**.
   - Valve body sub-assembly without handle extent: **$68.000\text{ mm} \times 61.189\text{ mm} \times 56.189\text{ mm}$**.
   - The previously cited $69.850\text{ mm} \times 54.500\text{ mm}$ represented the body-only bounding box under a rotated alignment frame.

---

## 2. Existing Reusable Modules vs Missing Modules

### A. Reusable Existing Modules
- [`src/cad/topology.py`](file:///c:/Users/abhil/Desktop/satven_freecad/src/cad/topology.py): B-Rep graph traversal, Face/Edge/Vertex adjacency extraction.
- [`src/cad/measurements.py`](file:///c:/Users/abhil/Desktop/satven_freecad/src/cad/measurements.py): Analytical surface recognition (Cylinder, Cone, Plane, Torus, BSpline) and analytical curve measurements.
- [`src/cad/features.py`](file:///c:/Users/abhil/Desktop/satven_freecad/src/cad/features.py): Feature recognition for holes, bosses, pockets, steps, fillets.
- [`src/cad/view_analysis.py`](file:///c:/Users/abhil/Desktop/satven_freecad/src/cad/view_analysis.py): View normal analysis and projected feature visibility.
- [`src/cad/section_cut_generator.py`](file:///c:/Users/abhil/Desktop/satven_freecad/src/cad/section_cut_generator.py): Finite slicing planes and cross-section wires.

### B. Missing / Required Modules for Phase 20
1. **`src/cad/brep_geometry_auditor.py` (Phase 20.1)**:
   - Deterministic assembly occurrence deduplication, surface/curve classification, and per-solid metric audit.
2. **`src/cad/view_intelligence.py` (Phase 20.4)**:
   - View usefulness scoring ($0.0 \text{ to } 1.0$), silhouette information entropy, and primary/secondary view selection.
3. **`src/cad/section_intelligence.py` (Phase 20.5 & 20.6)**:
   - Multi-type section candidate evaluator (Full, Half, Offset, Aligned), internal feature exposure scoring, and provenance linking.
4. **`src/cad/drawing_validator.py` (Phase 20.11)**:
   - Independent geometric verification of every dimension, section plane, hatch region, and center mark against the OCCT 3D model.
5. **Frontend Drawing Intelligence Panel (Phase 20.13)**:
   - Tabs: `[Views]`, `[Sections]`, `[Dimensions]`, `[Feature Graph]`, `[Geometry Evidence]`, `[Validation]`, `[Audit]`.

---

## 3. Risks & Mitigations

| Risk | Mitigation Strategy |
| :--- | :--- |
| **Assembly Duplication in STEP files** | Implement spatial geometry deduplication in `brep_geometry_auditor.py` comparing centroids, volumes, and bounding boxes. |
| **Arbitrary Heuristics / Magic Numbers** | Classify features strictly from OCCT analytical geometry (cylinder axis, normal direction, closed loops) rather than fixed thresholds. |
| **Non-finite Datum Planes ($2 \times 10^{100}\text{ mm}$)** | Maintain finite bounding box extraction filtering out infinite planar construction elements. |
| **Dimension & Text Collisions** | Implement ASME Y14.5 multi-tier staggered witness lines with bounding-box collision avoidance. |

---

## 4. Exact Incremental Implementation Plan

```
  [Step 1: Architecture Review & Technical Plan]  <-- CURRENT STEP
       │
  [Step 2: Phase 20.1 Exact B-Rep Geometry Auditor & Assembly Deduplication]
       │
  [Step 3: Phase 20.2 & 20.3 Engineering Feature Graph & Provenance Dimensions Engine]
       │
  [Step 4: Phase 20.4 View Intelligence & Usefulness Scoring]
       │
  [Step 5: Phase 20.5 - 20.7 Section Intelligence & Masked Hatching]
       │
  [Step 6: Phase 20.8 - 20.10 Dimension-to-View Association & Centerline Placement]
       │
  [Step 7: Phase 20.11 Independent Geometric Drawing Validator]
       │
  [Step 8: Phase 20.13 & 20.14 Frontend Drawing Intelligence Tabs & 3D Association]
       │
  [Step 9: Phase 20.15 Multi-Model Test Suite Execution (RB-3N-20A, Сборка1, Third STEP)]
```

---

## 5. Test Strategy

1. **Unit Tests**:
   - `tests/test_phase20_1_brep_geometry_audit.py` (Unique solids, envelope, analytical surfaces).
   - `tests/test_phase20_4_view_intelligence.py` (View scoring, primary/secondary ranking).
   - `tests/test_phase20_5_section_intelligence.py` (Full, Half, Offset section generation & feature exposure).
   - `tests/test_phase20_11_drawing_validator.py` (Geometric consistency checks, pass/fail reporting).
2. **Integration Verification**:
   - Automated end-to-end execution across 3 distinct STEP models: `RB-3N-20A.STEP`, `Сборка1.STEP`, and `Pieza18_1.STEP`.

---

## 6. Expected UI Changes

1. **New Tab Group in Drawing View**:
   - `[Views]` (View ranking & scores)
   - `[Sections]` (Section candidate list, cutting planes, exposed features)
   - `[Dimensions]` (Audited dimensions, source faces, tolerance, provenance)
   - `[Feature Graph]` (CAD features hierarchy)
   - `[Geometry Evidence]` (Exact B-Rep audit data)
   - `[Validation]` (Drawing validator pass/warning/error report)
   - `[Audit]` (Assembly solid breakdown & deduplication)
2. **Interactive 3D Highlighting**:
   - Clicking a dimension row in the Dimensions tab highlights its exact source B-Rep faces/edges in the Three.js 3D viewport.
