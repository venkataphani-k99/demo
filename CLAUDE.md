# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CAD Intelligence & Automation Engine — an engineering-grade CAD system that uses FreeCAD/OpenCASCADE (OCCT) for deterministic B-Rep geometry analysis, feature recognition, automated orthographic drawing generation, and AI-assisted engineering review. It runs on Python 3.11 via FreeCAD 1.1's bundled interpreter.

## Environment Setup

FreeCAD 1.1 is built against **Python 3.11**. Two options:

- **Option A (Recommended):** Use FreeCAD's built-in Python — zero config.
  ```powershell
  & "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_phase1_box.py
  ```

- **Option B:** Use a Python 3.11 Conda environment (e.g. `conda activate agrihub`).

## Running the Code

### CLI Pipelines (`src/main.py`)
```powershell
# Core STEP analysis (load -> B-Rep topology -> measurements -> features -> reports)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main input/Pieza18_1.STEP

# End-to-end 2D drawing -> 3D CAD reconstruction (Phases 17-19B)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main reconstruct output/Pieza18_1_complete_dimensioned.svg
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main reconstruct output/drawing.png --partial-mode
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main reconstruct output/drawing.png --workspace-dir ./workspaces

# Automated TechDraw drawing generation
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main draw input/Pieza18_1.STEP

# Dimension candidate generation + view visibility
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main dimensions input/Pieza18_1.STEP

# Dimension placement on TechDraw drawing
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main dimension-drawing input/Pieza18_1.STEP

# Complete engineering dimensioning
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main complete-dimensions input/Pieza18_1.STEP

# AI engineering review (mock/claude/gemini)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main ai-review input/Pieza18_1.STEP --provider mock
```

### FastAPI Server
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.api.app
# Serves at http://127.0.0.1:8000 with CORS for localhost:3000
```

### Tests
```powershell
# All tests (pytest)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m pytest tests\ -v

# Single test file
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_phase1_box.py
```

### Frontend
```powershell
cd frontend
npm install
npm run dev      # Vite dev server at localhost:3000
npm run test     # Vitest
```

## Architecture

The system has three major layers: **CAD Engine**, **Intelligence/AI Layer**, and **API/Frontend**.

### Two Parallel Use Cases

- **UC1 (3D→2D):** Load a STEP file → B-Rep analysis → automated orthographic drawing generation with dimension placement. All deterministic, no AI needed for geometry.
- **UC2 (2D→3D):** Upload an engineering drawing (PDF/PNG/SVG) → render to image → send to Claude + Gemini → consensus → feature synthesis → parametric reconstruction blueprint. Produces structured JSON understanding, **never** FreeCAD geometry (Phase 19B is permanently gated by the Hard 19B Gate).

### Phase Numbering

Phases describe the STEP-based pipeline (UC1) end-to-end:
- **Phase 1–6:** STEP loading, topology, measurements, feature recognition, dimension generation, TechDraw document creation
- **Phase 7:** Dimension placement engine (`dimension_placement.py`) — "safe subset" of 5 dimensions, hardcoded for Pieza18_1
- **Phase 8:** View analysis (`view_analysis.py`) — vector dot-product visibility scoring per orthographic view
- **Phase 9A:** Complete dimensioning (`complete_dimensioning.py`) — places all non-redundant dimensions. Contains a large `PIEZA18_1_PLACEMENT_SPECS` lookup table (dimension IDs → views, face refs, offsets) and hardcoded exclusion IDs. Only works for the benchmark drawing; offset defaults to (0,0) for any other model.
- **Phase 10–12:** AI engineering review, multimodal audit, engineering issues
- **Phase 13:** Regression testing, model validation, frontend consistency

Phases 17–19C describe the UC2 drawing-understanding pipeline (`src/drawing/`):
- **Phase 17:** Ingestion, rendering, multimodal analysis, consensus, validation
- **Phase 18/18.1:** Feature synthesis from drawing annotations → `FeatureGraph` with CSG blueprint
- **Phase 19A:** Parametric reconstruction plan with 4-tier provenance (Tier A→D)
- **Phase 19A.2:** Evidence auditor + Hard 19B Gate
- **Phase 19B:** CAD execution engine (`reconstruction_executor.py`) — respects the Hard 19B Gate; only EXECUTABLE steps produce real FreeCAD geometry; PARTIALLY_EXECUTABLE steps use placeholders; rest are skipped. Needs FreeCAD runtime.
- **Phase 19C (STEP Supplement Bridge):** `step_reference.py` extracts BRep geometry from the original STEP file (BBox, cylindrical features, holes, bosses). `drawing_reconstructor.py` supplements the drawing's feature graph with STEP dimensions (height Z, hole positions/depths, corrected depth Y). This bridges the gap where 2D drawings lack vertical callouts or position references. The STEP is ONLY a dimension reference — geometry is always rebuilt from scratch in FreeCAD.
- **Pipeline:** `pipeline.py` chains Phases 17→19C into `ReconstructionPipeline` class. Exposed via CLI as `python -m src.main reconstruct <drawing>`.

### CAD Engine (`src/cad/`)
Deterministic FreeCAD/OCCT modules — the single source of truth for all geometry. No LLM guesses dimensions.

Key flow: `step_loader` → `topology` (B-Rep adjacency graph) → `geometry` (surface/curve extraction) → `measurements` (exact OCCT measurements) → `features` (rule-based feature recognition) → `dimensions` (candidate dimension generation) → `view_analysis` (3D-to-2D projection visibility) → `dimension_placement` / `complete_dimensioning` (collision-free dimension placement on TechDraw) → `techdraw_generator` (automated orthographic drawing).

Additional CAD modules: `dimension_dependencies` (mathematical chain tracking), `dimension_redundancy` (redundancy filtering), `model_validator` (FCStd integrity), `drawing_svg_exporter`, `visual_debugger`, `view_analysis`.

**Note:** `complete_dimensioning.py` is NOT generic — it hardcodes `PIEZA18_1_PLACEMENT_SPECS` with face IDs, view assignments, and pixel offsets for the benchmark drawing. For any other model, all dimensions collapse to the view anchor center (dx=0, dy=0). The dimension-ID branching for D009/D010/D011 also assumes Pieza18_1's specific ID scheme.

### UC2 Drawing Understanding Pipeline (`src/drawing/`)
Completely separate from the CLI. API-only (`/drawing-projects` routes). Produces structured JSON — no FreeCAD geometry.

Flow: `ingestion.py` (file validation + immutable copy) → `renderer.py` (normalized PNG, 4-engine SVG fallback, 3-engine PDF fallback) → `multimodal_analyzer.py` (Claude + Gemini API calls with actual image payload) → `consensus.py` (deterministic bipartite matching, never auto-resolves disagreements) → `validator.py` (9 structural rules) → `feature_synthesizer.py` (evidence-driven feature classification with confidence scoring) → `reconstruction_planner.py` (ordered parametric CAD steps with provenance) → `reconstruction_auditor.py` (7-dimension evidence audit + Hard 19B Gate).

Key schemas: `schemas.py` (all Pydantic models — enums, DrawingSource, DrawingUnderstanding, FeatureGraph, etc.) and `reconstruction_schemas.py` (ParametricParameter, ParametricCADStep, ParametricReconstructionPlan, EvidenceAuditRecord).

**Note:** `constraint_analyzer.py` exists but is never called from the API route or any orchestration code — it's an unused module.

### Intelligence Layer (`src/intelligence/`)
Pluggable AI reasoning over deterministic CAD data. **Golden rule: LLMs must never invent geometry values.**

- `providers.py` — Abstract `EngineeringReasoningProvider` with `MockReasoningProvider`, `ClaudeReasoningProvider`, `GeminiReasoningProvider` implementations. Factory via `get_reasoning_provider()`.
- `pipeline.py` — `EngineeringIntelligencePipeline` orchestrates: (1) build CAD tool context, (2) invoke AI provider for dimension decisions, (3) run `DeterministicValidationGatekeeper` (9 strict checks: decision type, reason presence, candidate ID exists, exact numeric value match within 1e-3, unit correctness, source entity validity, feature ID validity, view validity, priority validity), (4) generate TechDraw with approved dimensions, (5) multimodal vision review.
- `tools.py` — `CADToolRegistry` wraps deterministic CAD operations as structured tools for AI consumption (model summary, features, dimension candidates, measurements, dependencies, coverage, datum detection).
- `decision_model.py` — Pydantic models: `EngineeringDecision`, `EngineeringReview`, `EngineeringRecommendation`, `DrawingDecisionSet`.
- `issue_engine.py` / `issues.py` — Engineering issue detection and recommendation generation from AI reviews with consensus logic.
- `review_engine.py` / `vision_reviewer.py` / `visual_reviewer.py` — Multimodal review with image analysis.

### API Layer (`src/api/`)
FastAPI service with routes under `/api/v1/`:

- `health`, `projects` (workspace management), `analysis` (full CAD analysis), `features`, `dimensions`, `drawings` (TechDraw generation), `artifacts`, `ai_review`, `issues`, `drawing_projects` (UC2 only).

Services (`src/api/services/`): `CadService` invokes the CLI pipeline via subprocess, `DrawingService` / `DrawingProjectService` handle drawing generation, `ProjectService` manages project metadata and artifacts.

### Frontend (`frontend/`)
React + TypeScript + Vite + Tailwind v4 + Three.js. Pages: `ProjectDashboard`, `DrawingDashboard`, `DrawingProjectsPage`, `ProjectsPage`. Components: `Viewer3D`, `DrawingViewer`, `DimensionsTable`, `FeaturesTable`, `AIReviewPanel`, `EngineeringIssuesPanel`.

## Key Data Contracts

- Input: STEP files (`.step`, `.STEP`) placed in `input/`
- Output: All artifacts in `output/` — `.FCStd` (editable FreeCAD docs), `.svg`, `.dxf`, `.json` (structured analysis), `.txt` (human-readable reports)
- `input/README.md` documents the input file format
- `.env` contains API keys (Gemini, Anthropic) — **never commit changes to `.env``

## Testing Philosophy

Tests are organized by phase (test_phaseN_*.py). Each is a standalone script that can be run directly with the FreeCAD Python interpreter — no test runner required. Most tests validate deterministic CAD output (counts, measurements, file integrity).

The UC2 evidence-gate tests (`test_phase19a2_evidence_gate.py`) use a hardcoded benchmark project ID (`6f8683f4-fec2-44e2-901b-84de173aea94`) and require the corresponding workspace to exist.

## Important Constraints

1. All geometry/math must come from OCCT — never calculated or guessed by LLMs
2. FreeCAD must be importable at module level (`freecad_env.py` auto-initializes on import)
3. Tests require a FreeCAD installation; they will fail without it
4. API keys in `.env` are required for live AI providers; use `--provider mock` for offline testing
5. Phase 19B uses the original STEP file as a dimension reference to fill drawing evidence gaps (height Z, hole positions, depths). The Hard 19B Gate still enforces strict evidence requirements, but the STEP bridge resolves the common gaps. Only still-unconstrained features (e.g., fillet edge selection for non-benchmark parts) remain gated.
6. `complete_dimensioning.py` is Pieza18_1-specific; it is not a generic dimension placement engine
