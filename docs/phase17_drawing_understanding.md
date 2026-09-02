# Phase 17 — 2D Engineering Drawing Understanding

## Overview

Phase 17 introduces Use Case 2 (UC2): ingesting an existing 2D engineering drawing (PDF, PNG, SVG) and converting its visual content into a structured, validated, AI-reviewed engineering understanding.

**Architectural boundary**: Phase 17 generates zero FreeCAD geometry. No `Part.Shape`, `.FCStd`, `.step`, or OCCT objects are created.

---

## Pipeline

```
Drawing file (PDF / PNG / SVG)
    │
    ▼
DrawingIngestion
  ├── Validates format (extension + magic bytes)
  ├── Computes SHA-256 of source
  ├── Records MIME, file size, page count, pixel dimensions
  ├── Saves immutable source copy to workspace
  └── Returns: DrawingSource
    │
    ▼
DrawingRenderer
  ├── PDF  → pymupdf / pdf2image / ghostscript → PNG (records quality level)
  ├── SVG  → cairosvg / Inkscape → PNG (records quality level)
  ├── PNG/JPEG → Pillow upscale to min 1200px long-edge → PNG
  └── Returns: RenderResult (png_path, width, height, sha256, quality)
    │
    ▼  (both branches in parallel)
    ├── DrawingMultimodalAnalyzer.analyze_with_claude()
    │     ├── Builds MultimodalRequestManifest (image_attached=True enforced)
    │     ├── Saves _multimodal_request_claude.json
    │     ├── Sends actual PNG as base64 image/png content block
    │     └── Returns: (manifest, ModelResult)
    │
    └── DrawingMultimodalAnalyzer.analyze_with_gemini()
          ├── Builds MultimodalRequestManifest (image_attached=True enforced)
          ├── Saves _multimodal_request_gemini.json
          ├── Sends actual PNG as inline_data image/png
          └── Returns: (manifest, ModelResult)
    │
    ▼
ConsensusEngine.compare(claude_result, gemini_result)
  ├── Views: matched by view_type → agreed / claude_only / gemini_only
  ├── Dimensions: matched by raw_text → agreed / unresolved / claude_only / gemini_only
  ├── Disagreements are PRESERVED — never auto-selected
  └── Returns: ConsensusResult
    │
    ▼
DrawingValidator.validate(understanding, img_w, img_h)
  ├── Checks: bbox within image bounds
  ├── Checks: normalized_value is finite and non-negative (except angles)
  ├── Checks: units are recognized engineering strings
  ├── Checks: view_id references exist
  ├── Checks: dimension_ids and entity_ids are unique
  ├── Checks: confidence in [0,1]
  ├── Checks: tolerance_text contains at least one digit
  └── Returns: (validated_understanding, error_list)
    │
    ▼
DrawingProjectService.save_understanding()
  ├── Saves {stem}_drawing_understanding.json
  ├── Saves {stem}_drawing_understanding.txt (human-readable)
  └── Updates project metadata
```

---

## API Endpoints

All endpoints under `/api/v1/drawing-projects/`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/drawing-projects` | Upload PDF/PNG/SVG → create UC2 project |
| `GET` | `/drawing-projects/{id}` | Get project status and metadata |
| `POST` | `/drawing-projects/{id}/analyze` | Run full UC2 pipeline |
| `GET` | `/drawing-projects/{id}/understanding` | Get full `DrawingUnderstanding` |
| `GET` | `/drawing-projects/{id}/artifacts/{artifact_id}` | Download artifact |

**Artifact IDs**: `normalized_png`, `source_drawing`, `understanding_json`, `understanding_txt`, `manifest_claude`, `manifest_gemini`.

---

## Multimodal Image Payload Verification

The `MultimodalRequestManifest.image_attached` field is a Pydantic validator that raises `ValueError` if set to `False`. This means:

- You cannot build a valid manifest without an actual image attached.
- The manifest is saved to disk **before** the API call is dispatched, proving the image was present.
- Any code path that bypasses image attachment will fail at manifest construction time, not silently at the model.

---

## Schema Summary

```python
DrawingUnderstanding
  ├── source: DrawingSource          # filename, mime, sha256, size, dimensions, timestamp
  ├── normalized_png_path: str       # path to PNG sent to AI models
  ├── normalized_png_sha256: str     # SHA-256 of that PNG
  ├── claude_manifest: MultimodalRequestManifest
  ├── gemini_manifest: MultimodalRequestManifest
  ├── claude_result: ModelResult     # views, dimensions, entities, title_block
  ├── gemini_result: ModelResult     # views, dimensions, entities, title_block
  ├── consensus: ConsensusResult     # agreed / disagreed / unresolved
  ├── validation_errors: list[ValidationError]
  └── validation_passed: bool
```

---

## Frontend Workflow

1. Click **"Drawing → Understanding"** tab in the navigation bar.
2. Drag-and-drop or browse for a PDF, PNG, JPEG, or SVG drawing file.
3. Click **"Upload Drawing"** → project is created.
4. Click **"Analyze Drawing with Claude + Gemini"** → pipeline runs (~30s).
5. Dashboard shows:
   - **Drawing Image** tab — original + normalized PNG side-by-side
   - **Detected Views** tab — view type, confidence, bbox per model
   - **Dimensions** tab — raw text, normalized value, unit, bbox per model
   - **Entities** tab — graphical entity types per model
   - **Title Block** tab — extracted metadata fields with confidence
   - **Model Comparison** tab — agreed (green) / unresolved (red) / solo (amber)
   - **Validation** tab — structural correctness errors and warnings

---

## Workspace Structure

```
workspaces/drawing_projects/{project_id}/
  drawing_project.json                     ← project metadata
  _upload_{filename}                       ← raw uploaded bytes
  {stem}_source.{ext}                      ← immutable source copy
  {stem}_normalized.png                    ← PNG sent to AI models
  {stem}_drawing_understanding.json        ← full DrawingUnderstanding
  {stem}_drawing_understanding.txt         ← human-readable summary
  {stem}_multimodal_request_claude.json    ← Claude manifest + prompt
  {stem}_multimodal_request_gemini.json    ← Gemini manifest + prompt
```

---

## Running Tests

```powershell
# Deterministic tests (no API keys needed)
python -m pytest tests/test_phase17_drawing_ingestion.py -v

# With reference drawing (requires UC1 pipeline to have run)
python -m pytest tests/test_phase17_drawing_ingestion.py -v -k "reference"

# Live provider tests (requires API keys)
python -m pytest tests/test_phase17_drawing_ingestion.py -v -m integration
```

---

## Known Limitations

1. **SVG rendering without cairosvg**: Without `cairosvg` or Inkscape installed, SVG is rendered to a placeholder PNG. AI model quality will be limited. Install `cairosvg` (`pip install cairosvg`) for full quality.
2. **PDF rendering without pymupdf**: Without `pymupdf`, `pdf2image`, or `ghostscript`, PDF is rendered to a placeholder. Install `pymupdf` (`pip install pymupdf`) for full quality.
3. **Phase 17 produces no 3D geometry**: The `DrawingUnderstanding` is a structured text/coordinate representation only. 3D reconstruction is a future Phase 18+ task.
4. **Model hallucinations**: The validator catches structural errors but cannot verify whether extracted dimensions correspond to actual visible callouts. Manual verification against the drawing image is always required.
5. **JPEG dimension detection**: JPEG pixel dimensions are parsed from SOF markers — works for standard JFIF/Exif files but may fail on unusual encodings.
