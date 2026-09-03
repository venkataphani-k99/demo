# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **FreeCAD 1.1** requires **Python 3.11**. Must be invoked via FreeCAD's bundled interpreter for any CAD operation.
- FreeCAD modules cannot be imported inside the FastAPI ASGI process directly — all CAD work must run in a subprocess using FreeCAD's Python.
- Project root (`C:\Users\abhil\Desktop\satven_freecad`) is added to `sys.path` in `src/main.py`.
- `.env` at repo root provides `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and provider model names. `frontend/.env` sets `VITE_API_BASE_URL`.

## Running the Code

### CLI — all via FreeCAD's Python

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main <command> [args]
```

| Command | Description |
|---|---|
| `analyse <step_file>` | Full pipeline: load STEP → B-Rep → features → reports |
| `draw <step_file>` | Automated TechDraw 5-view orthographic drawing |
| `dimensions <step_file>` | Dimension candidate generation + view visibility |
| `dimension-drawing <step_file>` | Phase 8: dimension placement on TechDraw |
| `complete-dimensions <step_file>` | Phase 9A: complete deterministic dimensioning |
| `reconstruct <drawing_file>` | Phase 17–19B: 2D drawing → 3D CAD reconstruction |
| `ai-review <step_file> --provider mock\|claude\|gemini` | AI engineering review |
| `engineering-review <step_file>` | Phase 12: engineering issues & recommendations |
| `mold-analysis <step_file>` | Phase 26: injection molding DFM |
| `mfg-review <step_file>` | Phase M1: manufacturing intelligence |

Output defaults to `output/`. Bare STEP path (no subcommand) runs `analyse`.

### FastAPI Server

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.api.app
# → http://127.0.0.1:8000 with CORS for localhost:3000
```

**Critical pattern:** API services (`src/api/services/cad_service.py`, `drawing_service.py`) invoke `src/main.py` via `subprocess.run()` with FreeCAD's Python. They never import FreeCAD directly. This is required to avoid DLL conflicts with Uvicorn's ASGI process.

### Frontend

```powershell
cd frontend
npm install
npm run dev      # Vite dev server at localhost:3000
npm run test     # Vitest
npm run build    # tsc && vite build
```

### Tests

```powershell
# All tests
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m pytest tests/ -v

# Single test (direct execution, no pytest needed)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_phase1_box.py
```

Tests are standalone scripts organized by phase number. They require FreeCAD's Python — they will fail with system Python.

## Architecture

### Two Independent Pipelines Sharing One Server

The FastAPI server hosts **two completely separate use cases** that share no code path:

**UC1 (3D→2D, Step-based):** Load a STEP file → B-Rep analysis → feature recognition → dimension generation → TechDraw orthographic drawing generation. Entirely deterministic — no LLM involved in geometry.

**UC2 (2D→3D, Drawing-based):** Upload a drawing (PDF/PNG/SVG) → render to image → send to Claude + Gemini → bipartite consensus → feature synthesis → parametric reconstruction blueprint. Produces structured JSON understanding only. Phase 19B execution is gated by the **Hard 19B Gate** — geometry is always rebuilt from scratch; the original STEP file is used only as a dimension reference (Phase 19C STEP Supplement Bridge).

### CAD Engine (`src/cad/`)

Deterministic FreeCAD/OCCT modules. The single source of truth for all geometry values.

`step_loader` → `topology` (B-Rep adjacency graph) → `geometry` (surface/curve extraction) → `measurements` (exact OCCT measurements) → `features` (rule-based recognition) → `dimensions` (candidate generation) → `view_analysis` (3D→2D projection visibility) → `dimension_placement` / `complete_dimensioning` (collision-free placement on TechDraw) → `techdraw_generator` (automated orthographic drawing).

`freecad_env.py` auto-initializes FreeCAD DLL paths on import. It also loads `.env` into `os.environ`.

### Intelligence Layer (`src/intelligence/`)

Pluggable AI reasoning over deterministic CAD data. **Golden rule: LLMs must never invent geometry values.**

- `providers.py` — Abstract `EngineeringReasoningProvider` with Mock, Claude, and Gemini implementations. Factory via `get_reasoning_provider()`.
- `tools.py` — `CADToolRegistry` wraps deterministic CAD operations as structured tools for AI consumption (model summary, features, dimensions, measurements, dependencies, coverage, datum detection).
- `pipeline.py` — `EngineeringIntelligencePipeline` orchestrates: build tool context → invoke AI → `DeterministicValidationGatekeeper` (9 strict checks including exact numeric value match within 1e-3) → generate TechDraw → multimodal vision review.
- `decision_model.py` — Pydantic models: `EngineeringDecision`, `EngineeringReview`, `EngineeringRecommendation`.
- `ai_reasoning/` — Phase 22 evidence validation and provider abstraction.
- `drawing_consistency/` — Phase 25 CAD↔Drawing consistency checking.

### UC2 Drawing Understanding (`src/drawing/`)

`pipeline.py` chains 7 stages: Ingest → Render → Claude+Gemini Analyze → Consensus → Validate → Feature Graph → Plan → Execute. Only the API layer calls this; the CLI `reconstruct` command is the only other entry point.

### Frontend (`frontend/`)

React 19 + TypeScript + Vite + Tailwind v4 + Three.js. URL-param-driven routing (`?mode=uc1|uc2&project=<id>&drawing=<id>`). Two pages per use case: project listing + dashboard. API clients in `lib/api.ts` (~1046 lines) and `lib/drawingApi.ts` (~471 lines).

## Key Constraints & Gotchas

1. **`complete_dimensioning.py` is Pieza18_1-specific.** It hardcodes `PIEZA18_1_PLACEMENT_SPECS` with face IDs, view assignments, and pixel offsets. For any other model, all dimensions collapse to the view anchor center (dx=0, dy=0).

2. **`drawing/constraint_analyzer.py` is unused** — never called from any API route or orchestration code.

3. **Duplicate module:** Both `src/cad/constraint_analyzer.py` and `src/drawing/constraint_analyzer.py` exist with different purposes.

4. **No build/deployment tooling** — no pyproject.toml, Docker, Makefile, or CI. Pure local development workflow.

5. **FreeCAD subprocess isolation** — the FastAPI server never imports FreeCAD. All CAD operations go through `src/main.py` invoked as a subprocess. The API services parse stdout for results.

6. **Tests require FreeCAD installation** — they import FreeCAD directly. Without FreeCAD 1.1 installed, tests will fail regardless of Python environment.

7. **The `MockReasoningProvider`** in `providers.py` uses `CompleteDimensioningEngine` to dynamically compute a dimension plan for any STEP file, not just Pieza18_1. The live Claude/Gemini providers pass raw candidate data to the API and rely on the LLM to make decisions — the `DeterministicValidationGatekeeper` enforces that all returned values match OCCT ground truth.
