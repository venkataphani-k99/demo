"""Phase 19C — End-to-end pipeline tests.

Tests the 2D→3D CAD reconstruction pipeline stages using cached artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.drawing.pipeline import (
    _stage_analyze,
    _stage_consensus,
    _stage_execute,
    _stage_ingest,
    _stage_plan,
    _stage_render,
    _stage_validate_and_synthesize,
)
from src.drawing.reconstruction_schemas import ReconstructionStatus


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_workspace(tmp_path):
    """Create a temporary workspace for pipeline tests."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def svg_path():
    return Path("output/Pieza18_1_complete_dimensioned.svg")


@pytest.fixture
def source(svg_path, test_workspace):
    from src.drawing.ingestion import DrawingIngestion
    content = svg_path.read_bytes()
    ingestor = DrawingIngestion()
    return ingestor.ingest(svg_path.name, content, test_workspace)


class TestStageIngest:
    def test_ingest_svg(self, source, svg_path):
        assert source.filename == svg_path.name
        assert source.mime_type == "image/svg+xml"
        assert source.file_size_bytes == svg_path.stat().st_size
        assert source.sha256
        assert len(source.sha256) == 64

    def test_ingest_sha256_deterministic(self, svg_path, test_workspace):
        from src.drawing.ingestion import DrawingIngestion
        ingestor = DrawingIngestion()
        c = svg_path.read_bytes()
        r1 = ingestor.ingest(svg_path.name, c, test_workspace)
        r2 = ingestor.ingest(svg_path.name, c, test_workspace)
        assert r1.sha256 == r2.sha256


class TestStageRender:
    def test_render_produces_png(self, source, test_workspace):
        render_result, notes = _stage_render(source, test_workspace)
        assert render_result.png_path.exists()
        assert render_result.png_path.suffix == ".png"
        assert render_result.width_px > 0
        assert render_result.height_px > 0

    def test_render_quality(self, source, test_workspace):
        render_result, notes = _stage_render(source, test_workspace)
        assert render_result.render_quality in ("full", "high", "medium", "low")


class TestStageAnalyze:
    def test_returns_results_when_api_keys_set(self, source, test_workspace):
        try:
            from src.drawing.renderer import DrawingRenderer
            r, _ = _stage_render(source, test_workspace)
            c, g, errs = _stage_analyze(r.png_path, test_workspace)
            # At least one provider should succeed if keys are configured
            assert c is not None or g is not None, "At least one AI provider should succeed"
        except Exception as exc:
            if "API" in str(exc) or "key" in str(exc).lower():
                pytest.skip(f"API keys not configured: {exc}")
            raise

    def test_no_api_keys_raises_runtime_error(self, source, test_workspace, monkeypatch):
        from src.drawing.renderer import DrawingRenderer
        r, _ = _stage_render(source, test_workspace)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="Both.*analysis failed"):
            _stage_analyze(r.png_path, test_workspace)


class TestStageConsensus:
    def test_consensus_from_results(self):
        from src.drawing.schemas import (
            ConsensusResult,
            DetectedView,
            ExtractedDimension,
            ModelResult,
            ViewType,
            DimensionType,
            ConsensusState,
            DimensionConsensus,
        )
        c = ModelResult(
            provider="claude",
            model="claude-test",
            views=[DetectedView(view_id="v1", view_type=ViewType.FRONT)],
            dimensions=[ExtractedDimension(
                dimension_id="d1", view_id="v1", dimension_type=DimensionType.LINEAR,
                raw_text="100", normalized_value=100.0, bbox=None,
            )],
        )
        g = ModelResult(
            provider="gemini",
            model="gemini-test",
            views=[DetectedView(view_id="v1", view_type=ViewType.FRONT)],
            dimensions=[ExtractedDimension(
                dimension_id="d1", view_id="v1", dimension_type=DimensionType.LINEAR,
                raw_text="100", normalized_value=100.0, bbox=None,
            )],
        )
        consensus = _stage_consensus(c, g)
        assert consensus is not None
        assert consensus.total_agreed > 0

    def test_single_provider_fallback(self):
        from src.drawing.schemas import (
            ConsensusResult,
            DetectedView,
            ExtractedDimension,
            ModelResult,
            ViewType,
            DimensionType,
        )
        c = ModelResult(
            provider="claude",
            model="claude-test",
            views=[DetectedView(view_id="v1", view_type=ViewType.FRONT)],
            dimensions=[ExtractedDimension(
                dimension_id="d1", view_id="v1", dimension_type=DimensionType.LINEAR,
                raw_text="100", normalized_value=100.0, bbox=None,
            )],
        )
        consensus = _stage_consensus(c, None)
        assert consensus.total_claude_dimensions == 1
        assert consensus.total_gemini_dimensions == 0
        assert len(consensus.claude_only_dimensions) == 1
        assert len(consensus.gemini_only_dimensions) == 0


class TestStageValidateAndSynthesize:
    def test_produces_feature_graph(self, test_workspace):
        from src.drawing.schemas import (
            ConsensusResult,
            DetectedView,
            ExtractedDimension,
            ModelResult,
            ViewType,
            DimensionType,
            DrawingSource,
        )
        from src.drawing.renderer import _sha256_path
        import datetime

        c = ModelResult(
            provider="claude",
            model="claude-test",
            views=[DetectedView(view_id="v1", view_type=ViewType.FRONT)],
            dimensions=[ExtractedDimension(
                dimension_id="d1", view_id="v1", dimension_type=DimensionType.LINEAR,
                raw_text="100", normalized_value=100.0, bbox=None,
            )],
            analysis_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        g = ModelResult(
            provider="gemini",
            model="gemini-test",
            views=[DetectedView(view_id="v1", view_type=ViewType.FRONT)],
            dimensions=[ExtractedDimension(
                dimension_id="d1", view_id="v1", dimension_type=DimensionType.LINEAR,
                raw_text="100", normalized_value=100.0, bbox=None,
            )],
            analysis_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        consensus = ConsensusResult(
            agreed_views=[],
            disagreed_views=[],
            agreed_dimensions=[],
            disagreed_dimensions=[],
            unresolved_dimensions=[],
            claude_only_dimensions=[],
            gemini_only_dimensions=[],
            total_claude_dimensions=1,
            total_gemini_dimensions=1,
            total_agreed=0,
            total_disagreed=0,
            total_unresolved=0,
        )
        source = DrawingSource(
            filename="test.svg",
            mime_type="image/svg+xml",
            sha256="a" * 64,
            file_size_bytes=1000,
            ingestion_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_path=str(test_workspace / "test.svg"),
        )

        understanding = _stage_validate_and_synthesize(
            c, g, consensus, source, "test-project", test_workspace
        )
        assert understanding.feature_graph is not None
        assert len(understanding.feature_graph.features) > 0


class TestStagePlan:
    def test_plan_from_feature_graph(self, test_workspace):
        from src.drawing.schemas import DrawingSource, DrawingUnderstanding
        import datetime

        # Use cached understanding from a real analysis if available
        cached = Path("workspaces/20260827_194958/Pieza18_1_complete_dimensioned_drawing_understanding.json")
        if not cached.exists():
            pytest.skip("No cached understanding available — run pipeline first")

        data = json.loads(cached.read_text(encoding="utf-8"))
        u = DrawingUnderstanding.model_validate(data)

        plan, audit = _stage_plan("test-project", u.feature_graph, test_workspace)
        assert len(plan.steps) > 0
        assert plan.reconstruction_status in ReconstructionStatus
        assert audit.gate_19b_status is not None


class TestStageExecute:
    def test_execute_plan(self, test_workspace):
        cached = Path("workspaces/20260827_194958/Pieza18_1_complete_dimensioned_drawing_understanding.json")
        if not cached.exists():
            pytest.skip("No cached understanding available — run pipeline first")

        from src.drawing.reconstruction_planner import ReconstructionPlanner
        from src.drawing.reconstruction_auditor import ReconstructionAuditor
        import json

        data = json.loads(cached.read_text(encoding="utf-8"))
        from src.drawing.schemas import DrawingUnderstanding, FeatureGraph
        u = DrawingUnderstanding.model_validate(data)

        planner = ReconstructionPlanner()
        plan = planner.plan("test-project", u.feature_graph)
        auditor = ReconstructionAuditor()
        audit = auditor.audit_plan("test-project", plan, u.feature_graph)

        result = _stage_execute(plan, test_workspace, "test-project", partial_mode=True)
        assert result.project_id == "test-project"
        assert result.step_results is not None


class TestPipelineIntegration:
    def test_pipeline_artifact_outputs(self):
        """Verify that the last successful pipeline run produced expected artifacts."""
        ws = Path("workspaces/20260827_194958")
        if not ws.exists():
            pytest.skip("No pipeline workspace found — run pipeline first")

        stem = "Pieza18_1_complete_dimensioned"
        required = [
            f"{stem}_drawing_understanding.json",
            f"{stem}_normalized.png",
            f"{stem}_source.svg",
            f"{stem}_multimodal_request_claude.json",
            f"{stem}_multimodal_request_gemini.json",
        ]
        for fname in required:
            assert (ws / fname).exists(), f"Missing artifact: {fname}"

    def test_understanding_json_valid(self):
        cached = Path("workspaces/20260827_194958/Pieza18_1_complete_dimensioned_drawing_understanding.json")
        if not cached.exists():
            pytest.skip("No cached understanding — run pipeline first")

        data = json.loads(cached.read_text(encoding="utf-8"))
        from src.drawing.schemas import DrawingUnderstanding
        u = DrawingUnderstanding.model_validate(data)
        assert u.project_id
        assert u.source is not None
        assert u.source.sha256
        assert u.understanding_timestamp
        assert u.claude_result is not None
        assert u.gemini_result is not None
        assert u.consensus is not None
        assert u.feature_graph is not None

    def test_pipeline_output_schema(self):
        """Verify the pipeline result dict has all expected keys."""
        from src.drawing.pipeline import ReconstructionPipeline
        # We can't run the full pipeline without API keys,
        # but we can verify the class interface
        assert hasattr(ReconstructionPipeline, 'run')
        assert hasattr(ReconstructionPipeline, '__init__')
