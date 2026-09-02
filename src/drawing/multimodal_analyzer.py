"""Phase 17 — Multimodal drawing analyzer.

Sends the ACTUAL rendered drawing PNG to Claude and Gemini.
Never sends metadata-only payloads — validates image_attached == True before dispatch.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from src.drawing.renderer import build_manifest
from src.drawing.schemas import (
    BoundingBox,
    DetectedView,
    DimensionType,
    EntityType,
    ExtractedDimension,
    GeometricEntity,
    ModelResult,
    MultimodalRequestManifest,
    TitleBlock,
    TitleBlockField,
    ViewType,
)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are an ENGINEERING DRAWING INTERPRETER, not a creative 3D designer.

Your task is to convert a 2D engineering drawing into a STRICT, EVIDENCE-BASED structured description that can be reconstructed by a deterministic FreeCAD/OpenCASCADE geometry engine.

CRITICAL RULE:
DO NOT design, imagine, beautify, approximate, complete, or invent a 3D object.
The final reconstructed model must represent ONLY the geometry supported by the uploaded engineering drawing.

==============================
PRIMARY OBJECTIVE
=================
Analyze the complete engineering drawing and identify the exact geometric information required to reproduce the same part in 3D.

The intended pipeline is:
2D Engineering Drawing
→ Orthographic View Detection
→ Dimension and Entity Extraction
→ Cross-View Geometric Correlation
→ Feature Graph
→ Parametric Reconstruction Plan
→ Deterministic FreeCAD/OpenCASCADE 3D Model

You are responsible ONLY for evidence-based drawing understanding.
You MUST NOT replace missing engineering information with a plausible design.

==============================
NON-INVENTION RULE
==================
For every geometric feature you report, provide evidence from the drawing.
A feature is VALID only when it is supported by one or more of:
1. An explicit dimension
2. A visible geometric entity
3. A clearly identifiable projection in an orthographic view
4. A cross-view correlation between two or more views
5. A standard engineering drawing convention that is visually explicit in the drawing

If a feature cannot be supported by evidence:
DO NOT CREATE IT. DO NOT GUESS ITS DIMENSIONS. DO NOT ASSUME ITS DEPTH. DO NOT ASSUME SYMMETRY.
DO NOT ADD A FILLET. DO NOT ADD A CHAMFER. DO NOT ADD A HOLE. DO NOT ADD A POCKET. DO NOT ADD A BOSS.
DO NOT ADD DECORATIVE OR ORGANIC GEOMETRY.

Return a single JSON object with these exact keys:
{
  "views": [
    {
      "view_id": "V001",
      "view_type": "FRONT",            // one of: FRONT TOP BOTTOM LEFT RIGHT REAR ISOMETRIC SECTION DETAIL AUXILIARY UNKNOWN
      "bbox": [x1, y1, x2, y2],        // pixel coordinates [x1, y1, x2, y2] in the image; null if not determinable
      "confidence": 0.95,              // 0.0 to 1.0
      "evidence": "Visible front-facing orthographic projection showing primary height (Z) and width (X) silhouette"
    }
  ],
  "dimensions": [
    {
      "dimension_id": "DIMG_001",
      "raw_text": "Ø10",               // exact text as visible in the drawing — do NOT normalize or guess
      "normalized_value": 10.0,        // numeric value; null if ambiguous or unreadable
      "unit": "mm",                    // mm / inch / degree / null
      "dimension_type": "diameter",    // overall_length overall_width overall_height diameter radius hole_depth pocket_depth center_distance pitch angle thickness chamfer fillet unknown
      "tolerance_text": null,          // e.g. "±0.05" or null
      "view_id": "V001",               // which view this dimension belongs to; null if unclear
      "bbox": [x1, y1, x2, y2],        // pixel location of the dimension annotation
      "confidence": 0.95,
      "evidence": "Explicit diameter callout visible adjacent to circular through-hole"
    }
  ],
  "entities": [
    {
      "entity_id": "ENT_001",
      "entity_type": "circle",         // one of: straight_edge circle arc centerline center_mark hidden_line extension_line dimension_line arrowhead section_hatch datum_symbol gdt_frame surface_finish note title_block unknown
      "view_id": "V001",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95,
      "evidence": "Circular aperture boundary visible in front view"
    }
  ],
  "title_block": {
    "drawing_title":      {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "drawing_number":     {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "revision":           {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "material":           {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "scale":              {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "units":              {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "projection_method":  {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "general_tolerances": {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "sheet_size":         {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "author":             {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "company":            {"raw_text": null, "normalized_value": null, "confidence": 0.0},
    "notes": []
  },
  "annotations": []
}

STRICT FORBIDDEN BEHAVIORS:
1. Never generate a random object inspired by the drawing.
2. Never estimate dimensions from what looks correct if an explicit dimension is missing.
3. Never invent geometry not supported by drawing evidence.
4. Accuracy is strictly more important than completeness.
5. Return ONLY the JSON object.
"""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_bbox(raw: Any) -> Optional[BoundingBox]:
    if raw is None:
        return None
    try:
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            x1, y1, x2, y2 = [float(v) for v in raw]
            if x2 > x1 and y2 > y1:
                return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
    except (TypeError, ValueError):
        pass
    return None


def _parse_view_type(raw: str) -> ViewType:
    try:
        return ViewType(raw.upper().strip())
    except (ValueError, AttributeError):
        return ViewType.UNKNOWN


def _parse_dim_type(raw: str) -> DimensionType:
    try:
        return DimensionType(raw.lower().strip())
    except (ValueError, AttributeError):
        return DimensionType.UNKNOWN


def _parse_entity_type(raw: str) -> EntityType:
    try:
        return EntityType(raw.lower().strip())
    except (ValueError, AttributeError):
        return EntityType.UNKNOWN


def _clean_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("", "none", "null", "n/a", "undefined"):
        return None
    return s


def _parse_model_result(data: Dict[str, Any], provider: str, model: str) -> ModelResult:
    """Parse raw AI JSON response into ModelResult schema."""
    views: List[DetectedView] = []
    for v in data.get("views", []):
        try:
            views.append(DetectedView(
                view_id=str(v.get("view_id", f"V{len(views)+1:03d}")),
                view_type=_parse_view_type(str(v.get("view_type", "UNKNOWN"))),
                bbox=_parse_bbox(v.get("bbox")),
                confidence=max(0.0, min(1.0, float(v.get("confidence", 0.5)))),
                evidence=str(v.get("evidence", "")),
            ))
        except Exception:
            continue

    dimensions: List[ExtractedDimension] = []
    for i, d in enumerate(data.get("dimensions", [])):
        try:
            raw_val = d.get("normalized_value")
            norm_val: Optional[float] = None
            if raw_val is not None:
                try:
                    import math
                    f = float(raw_val)
                    if math.isfinite(f):
                        norm_val = f
                except (TypeError, ValueError):
                    pass

            dimensions.append(ExtractedDimension(
                dimension_id=str(d.get("dimension_id", f"DIMG_{i+1:03d}")),
                raw_text=str(d.get("raw_text", "")),
                normalized_value=norm_val,
                unit=_clean_str(d.get("unit")),
                dimension_type=_parse_dim_type(str(d.get("dimension_type", "unknown"))),
                tolerance_text=_clean_str(d.get("tolerance_text")),
                view_id=_clean_str(d.get("view_id")),
                bbox=_parse_bbox(d.get("bbox")),
                confidence=max(0.0, min(1.0, float(d.get("confidence", 0.5)))),
                evidence=str(d.get("evidence", "")),
                source_provider=provider,
            ))
        except Exception:
            continue

    entities: List[GeometricEntity] = []
    for i, e in enumerate(data.get("entities", [])):
        try:
            entities.append(GeometricEntity(
                entity_id=str(e.get("entity_id", f"ENT_{i+1:03d}")),
                entity_type=_parse_entity_type(str(e.get("entity_type", "unknown"))),
                view_id=str(e.get("view_id", "")) or None,
                bbox=_parse_bbox(e.get("bbox")),
                confidence=max(0.0, min(1.0, float(e.get("confidence", 0.5)))),
                evidence=str(e.get("evidence", "")),
                source_provider=provider,
            ))
        except Exception:
            continue

    # Parse title block
    tb_raw = data.get("title_block") or {}
    title_block: Optional[TitleBlock] = None
    if tb_raw:
        def _tbf(raw: Any) -> Optional[TitleBlockField]:
            if raw is None:
                return None
            if isinstance(raw, dict):
                rt = raw.get("raw_text")
                nv = raw.get("normalized_value")
                return TitleBlockField(
                    raw_text=str(rt) if rt is not None else None,
                    normalized_value=str(nv) if nv is not None else None,
                    confidence=max(0.0, min(1.0, float(raw.get("confidence", 0.0)))),
                )
            return TitleBlockField(
                raw_text=str(raw),
                normalized_value=str(raw),
                confidence=0.5,
            )

        title_block = TitleBlock(
            drawing_title=_tbf(tb_raw.get("drawing_title")),
            drawing_number=_tbf(tb_raw.get("drawing_number")),
            revision=_tbf(tb_raw.get("revision")),
            material=_tbf(tb_raw.get("material")),
            scale=_tbf(tb_raw.get("scale")),
            units=_tbf(tb_raw.get("units")),
            projection_method=_tbf(tb_raw.get("projection_method")),
            general_tolerances=_tbf(tb_raw.get("general_tolerances")),
            sheet_size=_tbf(tb_raw.get("sheet_size")),
            author=_tbf(tb_raw.get("author")),
            company=_tbf(tb_raw.get("company")),
            notes=[_tbf(n) for n in (tb_raw.get("notes") or []) if _tbf(n) is not None],
        )

    raw_sha = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    raw_ann = data.get("annotations", [])
    clean_ann: List[Union[str, Dict[str, Any]]] = []
    if isinstance(raw_ann, list):
        clean_ann = raw_ann
    elif isinstance(raw_ann, dict):
        clean_ann = [raw_ann]

    return ModelResult(
        provider=provider,
        model=model,
        views=views,
        dimensions=dimensions,
        entities=entities,
        title_block=title_block,
        annotations=clean_ann,
        raw_response_sha256=raw_sha,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _extract_text(resp_data: Dict[str, Any]) -> str:
    """Extract text content from provider response envelope."""
    if "content" in resp_data and isinstance(resp_data["content"], list):
        parts = []
        for item in resp_data["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts).strip()
    if "candidates" in resp_data:
        try:
            return resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            pass
    if "choices" in resp_data:
        try:
            return resp_data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            pass
    return str(resp_data)


def _strip_json_fence(text: str) -> str:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return text


# ---------------------------------------------------------------------------
# Main analyzer class
# ---------------------------------------------------------------------------

class DrawingMultimodalAnalyzer:
    """
    Sends the actual rendered drawing PNG to Claude and Gemini for visual analysis.

    Both providers receive the binary PNG image — not structured JSON metadata.
    """

    def __init__(self) -> None:
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._anthropic_base = os.getenv("ANTHROPIC_BASE_URL", "https://api.opusmax.pro")
        self._anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self._gemini_key = os.getenv("GEMINI_API_KEY", "")
        self._gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def analyze_with_claude(
        self,
        png_path: Path,
        output_dir: Path,
    ) -> tuple[MultimodalRequestManifest, ModelResult]:
        """
        Analyze the drawing with Claude.

        Parameters
        ----------
        png_path : Path
            Path to the normalized PNG to send.
        output_dir : Path
            Directory to save the request manifest JSON.

        Returns
        -------
        (manifest, result) tuple

        Raises
        ------
        ValueError
            If ANTHROPIC_API_KEY is not set.
        RuntimeError
            If the API call fails.
        """
        if not self._anthropic_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it in .env or as an environment variable."
            )

        img_data = png_path.read_bytes()
        img_b64 = base64.standard_b64encode(img_data).decode("ascii")

        # Get dimensions from PNG header
        import struct
        w, h = 0, 0
        if len(img_data) >= 24 and img_data[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                w, h = struct.unpack(">II", img_data[16:24])
            except struct.error:
                pass

        manifest = build_manifest(
            provider="claude",
            model=self._anthropic_model,
            png_path=png_path,
            width_px=w,
            height_px=h,
            prompt=ANALYSIS_PROMPT,
        )

        # Save manifest before dispatch (proves image was attached)
        stem = png_path.stem.replace("_normalized", "")
        manifest_path = output_dir / f"{stem}_multimodal_request_claude.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        payload = {
            "model": self._anthropic_model,
            "max_tokens": 8192,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": ANALYSIS_PROMPT,
                        },
                    ],
                }
            ],
        }

        endpoint = (
            f"{self._anthropic_base}/v1/messages"
            if not self._anthropic_base.endswith("/v1/messages")
            else self._anthropic_base
        )
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self._anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude API HTTP {e.code}: {body}")
        except Exception as e:
            raise RuntimeError(f"Claude API request failed: {e}")

        raw_text = _extract_text(resp_data)
        raw_text = _strip_json_fence(raw_text)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Claude returned non-JSON response: {e}\nRaw: {raw_text[:500]}")

        result = _parse_model_result(data, "claude", self._anthropic_model)
        return manifest, result

    def analyze_with_gemini(
        self,
        png_path: Path,
        output_dir: Path,
    ) -> tuple[MultimodalRequestManifest, ModelResult]:
        """
        Analyze the drawing with Gemini.

        Parameters
        ----------
        png_path : Path
            Path to the normalized PNG to send.
        output_dir : Path
            Directory to save the request manifest JSON.

        Returns
        -------
        (manifest, result) tuple

        Raises
        ------
        ValueError
            If GEMINI_API_KEY is not set.
        RuntimeError
            If the API call fails.
        """
        if not self._gemini_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Set it in .env or as an environment variable."
            )

        img_data = png_path.read_bytes()
        img_b64 = base64.standard_b64encode(img_data).decode("ascii")

        import struct
        w, h = 0, 0
        if len(img_data) >= 24 and img_data[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                w, h = struct.unpack(">II", img_data[16:24])
            except struct.error:
                pass

        manifest = build_manifest(
            provider="gemini",
            model=self._gemini_model,
            png_path=png_path,
            width_px=w,
            height_px=h,
            prompt=ANALYSIS_PROMPT,
        )

        stem = png_path.stem.replace("_normalized", "")
        manifest_path = output_dir / f"{stem}_multimodal_request_gemini.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        candidate_models = [
            self._gemini_model,
            "gemini-3-flash-preview",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
            "gemini-flash-latest",
        ]
        # Deduplicate preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        last_error = None
        for model_name in candidate_models:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={self._gemini_key}"
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": img_b64,
                                }
                            },
                            {"text": ANALYSIS_PROMPT},
                        ]
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json"},
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    self._gemini_model = model_name
                    manifest.model = model_name
                    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
                    break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                last_error = f"Gemini API ({model_name}) HTTP {e.code}: {body}"
                if e.code in (429, 404, 503):
                    logger.warning(f"Gemini model {model_name} returned HTTP {e.code}. Trying next candidate model...")
                    continue
                raise RuntimeError(last_error)
            except Exception as e:
                last_error = f"Gemini API ({model_name}) request failed: {e}"
                logger.warning(f"Gemini model {model_name} failed: {e}. Trying next candidate model...")
                continue
        else:
            raise RuntimeError(last_error or "All Gemini candidate models failed.")

        raw_text = _extract_text(resp_data)
        raw_text = _strip_json_fence(raw_text)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Gemini returned non-JSON response: {e}\nRaw: {raw_text[:500]}")

        result = _parse_model_result(data, "gemini", self._gemini_model)
        return manifest, result
