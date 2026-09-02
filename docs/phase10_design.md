# Phase 10 Design: Engineering Drawing Intelligence Layer

## 1. Executive Summary & Core Philosophy

The goal of the **Engineering Drawing Intelligence Layer** is **NOT** to use AI to calculate CAD geometry, nor to estimate dimensions from visual pixels or LLM hallucinations. FreeCAD and OpenCASCADE (OCCT) already serve as the exact, deterministic mathematical authority.

The purpose of this layer is:
> **"Use an AI reasoning agent to determine engineering intent, select drawing views, prune redundant dimensions, and critique drawing presentation, while strictly using deterministic CAD tools as the single source of truth."**

```
                     ┌──────────────────────────────────────┐
                     │          3D CAD Model (STEP)         │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │      FreeCAD 1.1.3 + OpenCASCADE     │
                     │  Exact B-Rep / Topology / Geometry   │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │  Deterministic CAD Engines (Ph 1-9A) │
                     │  - Exact Measurements                │
                     │  - Feature Recognition               │
                     │  - Dimension Candidates              │
                     │  - Dependency & Redundancy Analysis  │
                     │  - Orthographic Projection Analysis  │
                     └──────────────────┬───────────────────┘
                                        │
                         Structured CAD Context (JSON)
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │     Engineering Reasoning Agent      │
                     │  (Claude 3.7 / Gemini 2.5 / Mock)    │
                     │  - Evaluates Engineering Intent      │
                     │  - Selects Include / Exclude / Defer │
                     │  - Explains Engineering Rationales   │
                     │  - Flags Ambiguities & Human Review  │
                     └──────────────────┬───────────────────┘
                                        │
                         Candidate Decisions (JSON)
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │  Deterministic Validation Gatekeeper │
                     │  - Verifies Candidate ID Exists      │
                     │  - Verifies Exact OCCT Value Matches │
                     │  - Verifies 3D B-Rep Entities Exist  │
                     │  - Verifies Collision & Margin Rules │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │      FreeCAD TechDraw Generator      │
                     │  Produces .FCStd, .svg, .dxf         │
                     └──────────────────┬───────────────────┘
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │  Multimodal Visual Review (Vision)   │
                     │  - Evaluates Sheet Readability       │
                     │  - Detects Visual Overlaps           │
                     │  - Suggests Visual Refinements       │
                     └──────────────────────────────────────┘
```

---

## 2. Division of Responsibility: AI vs. Deterministic CAD

| Functional Domain | FreeCAD / OCCT / Deterministic Engine | AI Reasoning Layer (Claude / Gemini / Mock) |
|:---|:---|:---|
| **Numeric Values** | **100% Authority**. Exact Euclidean distance, radii, diameters, depths. | **Zero Authority**. AI cannot invent or alter numeric values. |
| **B-Rep Topology** | Computes faces, edges, vertices, and dual connectivity graphs. | Consumes structured topology metadata. |
| **Feature Recognition** | Confirms geometry invariants (coaxiality, step faces, sweep angles). | Interprets functional purpose (e.g. clearance hole vs dowel pin hole). |
| **View Visibility** | Computes dot products between feature axes and camera vectors. | Decides which view best communicates manufacturing intent. |
| **Redundancy Pruning** | Detects mathematical additive chains ($D017 = D015 + D016$). | Formulates engineering explanations for why derived dimensions are omitted. |
| **Ambiguity Handling** | Detects incomplete sweeps ($61.3^\circ$ vaulted arch). | Explicitly flags ambiguous features for human engineering review. |
| **Visual Critique** | Renders vector drawing (.svg, .dxf) and sheet bounds. | Inspects layout aesthetics, visual clutter, and missing annotations. |

---

## 3. Tool-Based AI Interface (Agent Tool Registry)

The AI agent interacts with the CAD kernel exclusively through structured, programmatic tools. It never receives unconstrained raw memory or unstructured command-line access.

### Tool Registry Specification:

1. `get_model_summary()` $\rightarrow$ Units, solid count, bounding box extents, volume, surface area, and surface classification breakdown.
2. `get_features()` $\rightarrow$ List of recognized engineering features (`counterbored_hole`, `through_hole`, `external_boss`, `fillet`).
3. `get_feature(feature_id: str)` $\rightarrow$ Detailed geometry parameters, constituent B-Rep faces, axis vector, and position for a specific feature.
4. `get_dimension_candidates()` $\rightarrow$ All 20 candidate dimensions with raw OCCT values, units, semantics, and status.
5. `get_dimension(dimension_id: str)` $\rightarrow$ Exact B-Rep source entities, measurement method, axis, and visibility analysis.
6. `measure_distance(entity_a: str, entity_b: str)` $\rightarrow$ Exact mathematical Euclidean distance between two B-Rep entities.
7. `measure_angle(entity_a: str, entity_b: str)` $\rightarrow$ Exact angle between two face normals or feature axes in degrees.
8. `get_available_views()` $\rightarrow$ Standard orthographic views (`Front`, `Top`, `Left`, `Right`, `Bottom`) and camera vectors.
9. `get_view_visibility(candidate_id: str)` $\rightarrow$ Projection behavior per view (`circular_profile`, `edge_on`, `planar_profile`, `unsuitable`).
10. `get_datums()` $\rightarrow$ Discovered potential reference geometry (mounting base `Face16`, parallel end stops).
11. `get_dimension_dependencies()` $\rightarrow$ Additive chains, derived relationships, and geometric constraints.
12. `get_dimension_coverage()` $\rightarrow$ Current feature-by-feature dimensioning coverage status.
13. `place_dimension(dimension_id: str, view: str, x: float, y: float)` $\rightarrow$ Deterministic coordinate placement proposal.
14. `validate_dimension(dimension_id: str)` $\rightarrow$ Invariant check against 3D shape entities and measurement truth.
15. `validate_drawing()` $\rightarrow$ Full drawing check (sheet boundary compliance, pairwise collision distance $\ge 8\text{ mm}$).
16. `generate_drawing(dimension_ids: List[str])` $\rightarrow$ Compiles the approved drawing to `.FCStd`, `.svg`, and `.dxf`.

---

## 4. Engineering Intelligence Decision Contract (Schema)

Every decision returned by an AI provider conforms to the strict `EngineeringDecision` Pydantic model:

```json
{
  "dimension_id": "D001",
  "decision": "include",
  "priority": "PRIMARY",
  "reason": "Defines functional clearance bore diameter (Ø5.50 mm) for M5 fastener on counterbored feature CBORE_001.",
  "selected_view": "Top",
  "confidence": 0.98,
  "source_entities": ["Face4", "Face22"],
  "source_feature": "CBORE_001",
  "measurement_source": "OCCT",
  "exact_cad_value": 5.500,
  "unit": "mm",
  "requires_review": false,
  "review_flags": []
}
```

### Supported Decision States:
- **`include`**: Approved for placement on the TechDraw sheet.
- **`exclude`**: Omitted from drawing with an explicit rationale (e.g. derived sum $D017 = D015 + D016$, or duplicate measurement $D008$).
- **`defer`**: Valid candidate postponed for specialized secondary views or future detailing.
- **`ambiguous`**: Geometry semantics are uncertain (e.g. $D013$ partial $61.3^\circ$ vaulted arch). Automatically sets `requires_review = true`.
- **`requires_human_review`**: Triggers a notification flag for manual engineer inspection.

---

## 5. Multi-Model Architecture & Pluggable Providers

The reasoning layer is designed with a pluggable provider abstraction (`EngineeringReasoningProvider`):

1. **`MockReasoningProvider`** *(Default / Offline)*:
   - High-fidelity deterministic reference baseline.
   - Operates without internet connectivity or external API keys.
   - Implements strict rule-based expert logic to test the end-to-end intelligence contract.
2. **`ClaudeReasoningProvider`** *(Anthropic)*:
   - Supports latest Anthropic models (e.g. `claude-3-7-sonnet-20250219` and Claude 3.5 Sonnet).
   - Utilizes structured Tool Calling / Function Calling contracts with JSON schema output validation.
3. **`GeminiReasoningProvider`** *(Google)*:
   - Supports latest Gemini models (e.g. `gemini-2.5-pro` and `gemini-2.5-flash`).
   - Utilizes structured JSON mode and multimodal image review.

---

## 6. Deterministic Validation Gatekeeper

Before any AI decision is allowed to modify a TechDraw document, the **Validation Gatekeeper** executes the following immutable checks:

1. **ID Traceability**: The `dimension_id` must match a candidate generated by Phase 7.
2. **Value Integrity**: The decision's numeric value must match the exact OCCT measurement within $10^{-3}\text{ mm}$. If an LLM hallucinates an altered number, the decision is immediately rejected (`validation_failed`).
3. **B-Rep Entity Check**: All referenced `source_entities` must exist in the 3D model's face map.
4. **View Suitability Check**: The selected view must not have a visibility rating of `unsuitable`.
5. **Spatial Boundary & Collision Checks**: Dimension annotation coordinates must lie within printable margins ($10 \le X \le 410\text{ mm}$, $10 \le Y \le 287\text{ mm}$) and maintain $\ge 8\text{ mm}$ spacing from neighboring dimensions.

---

## 7. Multimodal Visual Critique Interface

The `DrawingVisionReviewer` interface allows vision-capable models (e.g. Gemini 2.5 Pro, Claude 3.7 Sonnet) to review rendered SVG/PNG sheets:

* **Inputs**:
  - Rendered drawing image (SVG/PNG of `DrawingPage`).
  - Structured engineering context JSON.
  - Placed dimension decisions.
* **Outputs**:
  - `visual_issues`: List of text collisions or leader line crossings.
  - `readability`: `"high"`, `"acceptable"`, or `"poor"`.
  - `missing_visible_annotations`: Suggestions for annotations that appear unlabelled.
  - `requires_review`: Boolean flag.

> **Safety Rule**: Visual observations can never override or invent CAD dimensions. Any missing feature identified visually must trigger a CAD tool query (`measure_distance` or `get_feature`) to obtain the exact mathematical value.

---

## 8. Human-in-the-Loop Review Triggers

The system automatically marks `requires_human_review = true` whenever:
1. Candidate status is `ambiguous` (e.g. $D013$ $46.00\text{ mm}$ partial vaulted arch).
2. AI confidence score $< 0.85$.
3. Feature requires a section view that has not yet been defined (`requires_section_view = true`).
4. Disagreement occurs between the AI proposal and the deterministic dependency graph.
5. Critical datum references are missing or unconfirmed.
