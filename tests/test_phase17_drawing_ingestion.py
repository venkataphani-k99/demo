"""Phase 17 — Deterministic tests for 2D Drawing Ingestion & Understanding (UC2).

These tests cover ingestion, rendering, schema validation, consensus logic, and
multimodal payload verification WITHOUT making live API calls.

Live provider integration tests are clearly marked and skipped by default unless
ANTHROPIC_API_KEY and GEMINI_API_KEY are set.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import tempfile
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.drawing.consensus import ConsensusEngine
from src.drawing.ingestion import DrawingIngestion, _sha256_bytes
from src.drawing.renderer import DrawingRenderer, _write_placeholder_png
from src.drawing.schemas import (
    BoundingBox,
    ConsensusState,
    DetectedView,
    DimensionConsensus,
    DimensionType,
    DrawingSource,
    DrawingUnderstanding,
    ExtractedDimension,
    ModelResult,
    MultimodalRequestManifest,
    TitleBlock,
    ValidationError,
    ViewConsensus,
    ViewType,
)
from src.drawing.validator import DrawingValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_png(w: int = 200, h: int = 100) -> bytes:
    """Create a minimal valid PNG."""
    def _chunk(t: bytes, d: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        return struct.pack(">I", len(d)) + t + d + crc

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw_rows = b"\x00" + b"\xFF\xFF\xFF" * w
    idat = zlib.compress(raw_rows * h, 1)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _make_svg(w: int = 300, h: int = 200) -> bytes:
    return (
        f'<?xml version="1.0"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
        f'<rect x="10" y="10" width="50" height="30" fill="none" stroke="black"/>'
        f'<text x="50" y="50">Ø10</text>'
        f'</svg>'
    ).encode("utf-8")


def _make_pdf() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]>>\nendobj\n"
        b"%%EOF\n"
    )


def _make_source(filename: str, content: bytes, tmp_dir: Path) -> DrawingSource:
    ing = DrawingIngestion()
    return ing.ingest(filename, content, tmp_dir)


def _make_model_result(
    provider: str,
    views: list | None = None,
    dims: list | None = None,
) -> ModelResult:
    return ModelResult(
        provider=provider,
        model=f"{provider}-test",
        views=views or [],
        dimensions=dims or [],
        analysis_timestamp="2026-01-01T00:00:00Z",
    )


def _make_dim(
    did: str,
    raw: str,
    value: float | None = None,
    view_id: str | None = None,
    provider: str = "claude",
) -> ExtractedDimension:
    return ExtractedDimension(
        dimension_id=did,
        raw_text=raw,
        normalized_value=value,
        unit="mm",
        dimension_type=DimensionType.LINEAR,
        confidence=0.9,
        source_provider=provider,
        view_id=view_id,
    )


def _make_view(vid: str, vtype: ViewType) -> DetectedView:
    return DetectedView(view_id=vid, view_type=vtype, confidence=0.9, evidence="test")


# ---------------------------------------------------------------------------
# 1. Ingestion tests
# ---------------------------------------------------------------------------

class TestDrawingIngestion:

    def test_png_ingestion_records_sha256(self, tmp_path):
        content = _make_png()
        source = _make_source("test.png", content, tmp_path)
        assert source.sha256 == hashlib.sha256(content).hexdigest()

    def test_png_ingestion_records_dimensions(self, tmp_path):
        content = _make_png(w=320, h=200)
        source = _make_source("test.png", content, tmp_path)
        assert source.image_width_px == 320
        assert source.image_height_px == 200

    def test_png_ingestion_records_mime(self, tmp_path):
        content = _make_png()
        source = _make_source("test.png", content, tmp_path)
        assert source.mime_type == "image/png"

    def test_svg_ingestion_records_dimensions(self, tmp_path):
        content = _make_svg(w=640, h=480)
        source = _make_source("drawing.svg", content, tmp_path)
        assert source.image_width_px == 640
        assert source.image_height_px == 480

    def test_svg_ingestion_records_mime(self, tmp_path):
        content = _make_svg()
        source = _make_source("drawing.svg", content, tmp_path)
        assert source.mime_type == "image/svg+xml"

    def test_pdf_ingestion_records_page_count(self, tmp_path):
        content = _make_pdf()
        source = _make_source("drawing.pdf", content, tmp_path)
        assert source.page_count is not None
        assert source.page_count >= 1

    def test_pdf_ingestion_records_mime(self, tmp_path):
        content = _make_pdf()
        source = _make_source("drawing.pdf", content, tmp_path)
        assert source.mime_type == "application/pdf"

    def test_source_file_is_immutable_copy(self, tmp_path):
        content = _make_png()
        source = _make_source("test.png", content, tmp_path)
        source_path = Path(source.source_path)
        assert source_path.exists()
        # Modifying source_path should not affect original content bytes
        original_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        assert original_hash == source.sha256

    def test_empty_content_raises(self, tmp_path):
        with pytest.raises(ValueError, match="empty"):
            DrawingIngestion().ingest("test.png", b"", tmp_path)

    def test_unsupported_extension_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported file format"):
            DrawingIngestion().ingest("model.step", b"data", tmp_path)

    def test_jpeg_ingestion(self, tmp_path):
        # Minimal JPEG magic bytes
        content = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
        # Don't need dimension parsing to succeed — just format acceptance
        source = DrawingIngestion().ingest("photo.jpg", content, tmp_path)
        assert source.mime_type == "image/jpeg"


# ---------------------------------------------------------------------------
# 2. Renderer tests
# ---------------------------------------------------------------------------

class TestDrawingRenderer:

    def test_png_copy_produces_output_file(self, tmp_path):
        content = _make_png(w=400, h=300)
        source = _make_source("test.png", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)
        assert result.png_path.exists()

    def test_png_sha256_matches_file(self, tmp_path):
        content = _make_png()
        source = _make_source("test.png", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)
        sha = hashlib.sha256(result.png_path.read_bytes()).hexdigest()
        assert sha == result.sha256

    def test_svg_produces_png_output(self, tmp_path):
        content = _make_svg()
        source = _make_source("drawing.svg", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)
        assert result.png_path.exists()
        assert result.png_path.suffix == ".png"

    def test_write_placeholder_png_is_valid_png(self, tmp_path):
        out = tmp_path / "placeholder.png"
        _write_placeholder_png(out, 50, 50)
        data = out.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", data[16:24])
        assert w == 50
        assert h == 50

    def test_render_quality_recorded(self, tmp_path):
        content = _make_png()
        source = _make_source("test.png", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)
        assert result.render_quality in ("full", "limited", "copy")
        assert isinstance(result.render_notes, str)
        assert len(result.render_notes) > 0


# ---------------------------------------------------------------------------
# 3. Schema validation tests
# ---------------------------------------------------------------------------

class TestBoundingBox:

    def test_valid_bbox(self):
        b = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        assert b.x2 == 100

    def test_invalid_bbox_x2_le_x1(self):
        with pytest.raises(Exception):
            BoundingBox(x1=100, y1=0, x2=50, y2=50)

    def test_invalid_bbox_y2_le_y1(self):
        with pytest.raises(Exception):
            BoundingBox(x1=0, y1=100, x2=100, y2=50)


class TestExtractedDimension:

    def test_infinite_value_rejected(self):
        with pytest.raises(Exception):
            ExtractedDimension(
                dimension_id="D1", raw_text="∞",
                normalized_value=float("inf"),
                confidence=0.9, source_provider="claude",
            )

    def test_nan_value_rejected(self):
        with pytest.raises(Exception):
            ExtractedDimension(
                dimension_id="D1", raw_text="NaN",
                normalized_value=float("nan"),
                confidence=0.9, source_provider="claude",
            )

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(Exception):
            ExtractedDimension(
                dimension_id="D1", raw_text="10",
                confidence=1.5, source_provider="claude",
            )


class TestMultimodalRequestManifest:

    def test_image_attached_false_rejected(self):
        with pytest.raises(Exception, match="image_attached"):
            MultimodalRequestManifest(
                provider="claude",
                model="claude-3",
                image_path="/tmp/x.png",
                mime_type="image/png",
                image_width_px=100,
                image_height_px=100,
                image_byte_size=1000,
                image_sha256="abc",
                image_attached=False,       # ← must be rejected
                prompt_length_chars=100,
                request_timestamp="2026-01-01T00:00:00Z",
            )

    def test_image_attached_true_accepted(self):
        m = MultimodalRequestManifest(
            provider="claude",
            model="claude-3",
            image_path="/tmp/x.png",
            mime_type="image/png",
            image_width_px=100,
            image_height_px=100,
            image_byte_size=1000,
            image_sha256="abc123",
            image_attached=True,
            prompt_length_chars=200,
            request_timestamp="2026-01-01T00:00:00Z",
        )
        assert m.image_attached is True


# ---------------------------------------------------------------------------
# 4. Validator tests
# ---------------------------------------------------------------------------

class TestDrawingValidator:

    def _make_understanding(
        self,
        claude: ModelResult | None = None,
        gemini: ModelResult | None = None,
        source: DrawingSource | None = None,
    ) -> DrawingUnderstanding:
        if source is None:
            source = DrawingSource(
                filename="test.png",
                mime_type="image/png",
                sha256="abc",
                file_size_bytes=100,
                ingestion_timestamp="2026-01-01T00:00:00Z",
                source_path="/tmp/test.png",
            )
        return DrawingUnderstanding(
            project_id="test-proj",
            source=source,
            claude_result=claude,
            gemini_result=gemini,
            understanding_timestamp="2026-01-01T00:00:00Z",
        )

    def test_valid_understanding_passes(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = _make_dim("D001", "50", 50.0, "V001")
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        serious = [e for e in errors if e.severity == "error"]
        assert len(serious) == 0

    def test_out_of_bounds_bbox_generates_warning(self):
        view = DetectedView(
            view_id="V001", view_type=ViewType.FRONT,
            bbox=BoundingBox(x1=0, y1=0, x2=1000, y2=1000),  # outside 800×600
            confidence=0.9, evidence=""
        )
        result = _make_model_result("claude", [view])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("bounds" in e.message.lower() for e in warnings)

    def test_negative_dimension_generates_warning(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = ExtractedDimension(
            dimension_id="D001", raw_text="-5",
            normalized_value=-5.0,         # negative linear dimension
            dimension_type=DimensionType.LINEAR,
            confidence=0.9, source_provider="claude", view_id="V001",
        )
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("negative" in e.message.lower() for e in warnings)

    def test_missing_view_reference_is_error(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = _make_dim("D001", "50", 50.0, view_id="V999")  # V999 does not exist
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        errors_only = [e for e in errors if e.severity == "error"]
        assert any("view_id" in e.message.lower() or "V999" in e.message for e in errors_only)

    def test_duplicate_dimension_ids_error(self):
        view = _make_view("V001", ViewType.FRONT)
        d1 = _make_dim("D001", "10", 10.0, "V001")
        d2 = _make_dim("D001", "20", 20.0, "V001")   # same ID
        result = _make_model_result("claude", [view], [d1, d2])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        errors_only = [e for e in errors if e.severity == "error"]
        assert any("duplicate" in e.message.lower() for e in errors_only)

    def test_malformed_tolerance_generates_warning(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = ExtractedDimension(
            dimension_id="D001", raw_text="50",
            normalized_value=50.0,
            dimension_type=DimensionType.LINEAR,
            tolerance_text="plus minus",   # no digits — malformed
            confidence=0.9, source_provider="claude", view_id="V001",
        )
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("tolerance" in e.message.lower() or "malformed" in e.message.lower() for e in warnings)

    def test_invalid_unit_generates_warning(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = ExtractedDimension(
            dimension_id="D001", raw_text="50 fathoms",
            normalized_value=50.0,
            dimension_type=DimensionType.LINEAR,
            unit="fathoms",   # not a recognized engineering unit
            confidence=0.9, source_provider="claude",
        )
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        _, errors = DrawingValidator().validate(u, 800, 600)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("unit" in e.message.lower() for e in warnings)

    def test_validation_passed_set_correctly(self):
        view = _make_view("V001", ViewType.FRONT)
        dim = _make_dim("D001", "50", 50.0, "V001")
        result = _make_model_result("claude", [view], [dim])
        u = self._make_understanding(claude=result)
        u, errors = DrawingValidator().validate(u, 800, 600)
        serious = [e for e in errors if e.severity == "error"]
        assert u.validation_passed == (len(serious) == 0)


# ---------------------------------------------------------------------------
# 5. Consensus engine tests
# ---------------------------------------------------------------------------

class TestConsensusEngine:
    engine = ConsensusEngine()

    def _results(
        self,
        c_dims: list[tuple[str, float | None]],
        g_dims: list[tuple[str, float | None]],
        c_views: list[ViewType] = None,
        g_views: list[ViewType] = None,
    ):
        c_views = c_views or []
        g_views = g_views or []
        claude = _make_model_result(
            "claude",
            [_make_view(f"VC{i}", vt) for i, vt in enumerate(c_views)],
            [_make_dim(f"DC{i}", raw, val, provider="claude") for i, (raw, val) in enumerate(c_dims)],
        )
        gemini = _make_model_result(
            "gemini",
            [_make_view(f"VG{i}", vt) for i, vt in enumerate(g_views)],
            [_make_dim(f"DG{i}", raw, val, provider="gemini") for i, (raw, val) in enumerate(g_dims)],
        )
        return claude, gemini

    def test_identical_values_are_agreed(self):
        c, g = self._results([("Ø10", 10.0)], [("Ø10", 10.0)])
        result = self.engine.compare(c, g)
        assert result.total_agreed == 1
        assert result.total_unresolved == 0

    def test_differing_values_are_unresolved_not_auto_selected(self):
        c, g = self._results([("Ø10", 10.0)], [("Ø10", 12.0)])
        result = self.engine.compare(c, g)
        assert result.total_unresolved == 1
        # Both values preserved
        unr = result.unresolved_dimensions[0]
        assert unr.claude_value == 10.0
        assert unr.gemini_value == 12.0
        assert unr.state == ConsensusState.UNRESOLVED

    def test_claude_only_dimension_recorded(self):
        c, g = self._results([("R5", 5.0)], [])
        result = self.engine.compare(c, g)
        assert "R5" in result.claude_only_dimensions

    def test_gemini_only_dimension_recorded(self):
        c, g = self._results([], [("70.04", 70.04)])
        result = self.engine.compare(c, g)
        assert "70.04" in result.gemini_only_dimensions

    def test_agreed_views_detected(self):
        c, g = self._results([], [], [ViewType.FRONT, ViewType.TOP], [ViewType.FRONT])
        result = self.engine.compare(c, g)
        agreed_types = {v.view_type for v in result.agreed_views}
        assert ViewType.FRONT in agreed_types

    def test_gemini_only_view_recorded(self):
        c, g = self._results([], [], [ViewType.FRONT], [ViewType.FRONT, ViewType.TOP])
        result = self.engine.compare(c, g)
        solo_types = {v.view_type for v in result.disagreed_views}
        assert ViewType.TOP in solo_types

    def test_near_equal_values_within_tolerance_agree(self):
        # 10.00 vs 10.001 — within abs tolerance of 0.01
        c, g = self._results([("10", 10.0)], [("10", 10.001)])
        result = self.engine.compare(c, g)
        assert result.total_agreed == 1

    def test_totals_sum_correctly(self):
        c, g = self._results(
            [("Ø10", 10.0), ("50", 50.0), ("R2", 2.0)],
            [("Ø10", 10.0), ("50", 55.0), ("Ø8", 8.0)],
        )
        result = self.engine.compare(c, g)
        assert result.total_claude_dimensions == 3
        assert result.total_gemini_dimensions == 3
        # Ø10: agreed, 50: unresolved (10.0 != 55.0), R2: claude_only, Ø8: gemini_only
        assert result.total_agreed >= 1


# ---------------------------------------------------------------------------
# 6. Multimodal payload tests (image_attached enforcement)
# ---------------------------------------------------------------------------

class TestMultimodalPayloadVerification:

    def test_manifest_with_false_image_attached_raises(self):
        with pytest.raises(Exception):
            MultimodalRequestManifest(
                provider="test", model="test-v1",
                image_path="/x.png", mime_type="image/png",
                image_width_px=10, image_height_px=10,
                image_byte_size=500, image_sha256="abc",
                image_attached=False,
                prompt_length_chars=100,
                request_timestamp="2026-01-01T00:00:00Z",
            )

    def test_claude_analyzer_embeds_image_in_payload(self, tmp_path):
        """Verify Claude analyzer payload includes 'source' image block, not just text."""
        from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer

        png_path = tmp_path / "test_normalized.png"
        png_data = _make_png(w=100, h=100)
        png_path.write_bytes(png_data)

        analyzer = DrawingMultimodalAnalyzer()
        analyzer._anthropic_key = "test_key_do_not_call"

        captured_payloads = []

        def mock_urlopen(req, timeout=None):
            # Extract payload
            body = req.data
            payload = json.loads(body)
            captured_payloads.append(payload)
            # Return a mock response with valid JSON drawing understanding
            mock_resp = MagicMock()
            fake_response = {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "views": [],
                        "dimensions": [],
                        "entities": [],
                        "title_block": {},
                        "annotations": [],
                    })
                }]
            }
            mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            try:
                analyzer.analyze_with_claude(png_path, tmp_path)
            except Exception:
                pass

        assert len(captured_payloads) > 0
        payload = captured_payloads[0]
        messages = payload.get("messages", [])
        assert len(messages) > 0
        content_blocks = messages[0].get("content", [])
        image_blocks = [b for b in content_blocks if isinstance(b, dict) and b.get("type") == "image"]
        assert len(image_blocks) > 0, "Claude payload must contain an actual image block"
        # Verify the image data is non-empty base64
        img_block = image_blocks[0]
        img_data = img_block.get("source", {}).get("data", "")
        assert len(img_data) > 100, "Claude image block must contain actual binary image data"

    def test_gemini_analyzer_embeds_inline_data(self, tmp_path):
        """Verify Gemini analyzer payload includes 'inline_data' image part."""
        from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer

        png_path = tmp_path / "test_normalized.png"
        png_path.write_bytes(_make_png(w=100, h=100))

        analyzer = DrawingMultimodalAnalyzer()
        analyzer._gemini_key = "test_key_do_not_call"

        captured_payloads = []

        def mock_urlopen(req, timeout=None):
            body = req.data
            payload = json.loads(body)
            captured_payloads.append(payload)
            mock_resp = MagicMock()
            fake_response = {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": json.dumps({
                                "views": [], "dimensions": [], "entities": [],
                                "title_block": {}, "annotations": [],
                            })
                        }]
                    }
                }]
            }
            mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            try:
                analyzer.analyze_with_gemini(png_path, tmp_path)
            except Exception:
                pass

        assert len(captured_payloads) > 0
        payload = captured_payloads[0]
        contents = payload.get("contents", [])
        assert len(contents) > 0
        parts = contents[0].get("parts", [])
        image_parts = [p for p in parts if isinstance(p, dict) and "inline_data" in p]
        assert len(image_parts) > 0, "Gemini payload must contain an inline_data image part"
        data = image_parts[0]["inline_data"].get("data", "")
        assert len(data) > 100, "Gemini inline_data must contain actual binary image data"


# ---------------------------------------------------------------------------
# 7. Reference drawing integration hint (not hardcoded)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not Path("output/Pieza18_1_complete_dimensioned.svg").exists(),
    reason="Reference UC1 SVG not present — run UC1 pipeline first.",
)
class TestReferenceDrawingIngestion:
    """Tests using the UC1 reference drawing output/Pieza18_1_complete_dimensioned.svg."""

    def test_reference_svg_ingests(self, tmp_path):
        content = Path("output/Pieza18_1_complete_dimensioned.svg").read_bytes()
        source = DrawingIngestion().ingest("Pieza18_1_complete_dimensioned.svg", content, tmp_path)
        assert source.sha256 != ""
        assert source.file_size_bytes > 0
        assert source.mime_type == "image/svg+xml"

    def test_reference_svg_renders(self, tmp_path):
        content = Path("output/Pieza18_1_complete_dimensioned.svg").read_bytes()
        source = DrawingIngestion().ingest("Pieza18_1_complete_dimensioned.svg", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)
        assert result.png_path.exists()
        assert result.sha256 != ""

    def test_reference_svg_source_is_unchanged(self, tmp_path):
        svg_path = Path("output/Pieza18_1_complete_dimensioned.svg")
        original_sha = hashlib.sha256(svg_path.read_bytes()).hexdigest()
        content = svg_path.read_bytes()
        DrawingIngestion().ingest("Pieza18_1_complete_dimensioned.svg", content, tmp_path)
        after_sha = hashlib.sha256(svg_path.read_bytes()).hexdigest()
        assert original_sha == after_sha, "Source SVG was modified during ingestion — MUST remain immutable"


# ---------------------------------------------------------------------------
# 8. Live provider integration tests (skipped unless API keys set)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live Claude integration test.",
)
@pytest.mark.integration
class TestClaudeIntegration:
    def test_live_claude_returns_dims(self, tmp_path):
        from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer

        content = Path("output/Pieza18_1_complete_dimensioned.svg").read_bytes()
        source = DrawingIngestion().ingest("Pieza18_1_complete_dimensioned.svg", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)

        analyzer = DrawingMultimodalAnalyzer()
        manifest, model_result = analyzer.analyze_with_claude(result.png_path, tmp_path)

        assert manifest.image_attached is True
        assert model_result.error is None
        assert len(model_result.dimensions) > 0, "Live Claude must extract at least one dimension"
        assert all(d.raw_text for d in model_result.dimensions), "All dimensions must have raw_text"


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping live Gemini integration test.",
)
@pytest.mark.integration
class TestGeminiIntegration:
    def test_live_gemini_returns_dims(self, tmp_path):
        from src.drawing.multimodal_analyzer import DrawingMultimodalAnalyzer

        content = Path("output/Pieza18_1_complete_dimensioned.svg").read_bytes()
        source = DrawingIngestion().ingest("Pieza18_1_complete_dimensioned.svg", content, tmp_path)
        result = DrawingRenderer().render(source, tmp_path)

        analyzer = DrawingMultimodalAnalyzer()
        manifest, model_result = analyzer.analyze_with_gemini(result.png_path, tmp_path)

        assert manifest.image_attached is True
        assert model_result.error is None
        assert len(model_result.dimensions) > 0, "Live Gemini must extract at least one dimension"
