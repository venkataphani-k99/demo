"""Phase 17 — Drawing Project Service: manages UC2 workspaces."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.drawing.schemas import (
    DrawingProjectCreateResponse,
    DrawingProjectStatusResponse,
    DrawingUnderstanding,
)

# Workspace root for UC2 drawing projects (isolated from UC1)
_WORKSPACE_ROOT = Path("workspaces") / "drawing_projects"


class DrawingProjectService:
    """Manages UC2 drawing project workspaces and metadata."""

    def _project_dir(self, project_id: str) -> Path:
        return _WORKSPACE_ROOT / project_id

    def _meta_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "drawing_project.json"

    def _load_meta(self, project_id: str) -> Dict[str, Any]:
        mp = self._meta_path(project_id)
        if not mp.exists():
            raise FileNotFoundError(f"Drawing project '{project_id}' not found.")
        return json.loads(mp.read_text(encoding="utf-8"))

    def _save_meta(self, project_id: str, meta: Dict[str, Any]) -> None:
        pdir = self._project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        mp = self._meta_path(project_id)
        tmp = mp.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            tmp.replace(mp)
        except OSError:
            mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def list_projects(self) -> list[Dict[str, Any]]:
        if not _WORKSPACE_ROOT.exists():
            return []
        projects = []
        for pdir in _WORKSPACE_ROOT.iterdir():
            if pdir.is_dir():
                mp = pdir / "drawing_project.json"
                if mp.exists():
                    try:
                        meta = json.loads(mp.read_text(encoding="utf-8"))
                        projects.append(meta)
                    except Exception:
                        pass
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

    def create_project(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Create a new UC2 drawing project workspace."""
        project_id = str(uuid.uuid4())
        pdir = self._project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        meta: Dict[str, Any] = {
            "project_id": project_id,
            "filename": filename,
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "analysis_complete": False,
            "artifacts": {},
        }
        self._save_meta(project_id, meta)

        # Save the raw uploaded content for ingestion
        raw_path = pdir / f"_upload_{filename}"
        raw_path.write_bytes(content)
        meta["raw_upload_path"] = str(raw_path)
        self._save_meta(project_id, meta)

        return meta

    def get_project_metadata(self, project_id: str) -> Dict[str, Any]:
        return self._load_meta(project_id)

    def get_project_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id)

    def update_status(self, project_id: str, status: str, error: str = "") -> None:
        meta = self._load_meta(project_id)
        meta["status"] = status
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            meta["error_message"] = error
        self._save_meta(project_id, meta)

    def save_understanding(
        self, project_id: str, understanding: DrawingUnderstanding
    ) -> Path:
        """Persist the DrawingUnderstanding JSON artifact."""
        pdir = self._project_dir(project_id)
        stem = Path(understanding.source.filename).stem
        json_path = pdir / f"{stem}_drawing_understanding.json"
        json_path.write_text(understanding.model_dump_json(indent=2), encoding="utf-8")

        # Human-readable text summary
        txt_path = pdir / f"{stem}_drawing_understanding.txt"
        txt_path.write_text(self._build_summary(understanding), encoding="utf-8")

        # Update metadata
        meta = self._load_meta(project_id)
        meta["analysis_complete"] = True
        meta["status"] = "analyzed"
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        meta["artifacts"]["understanding_json"] = {
            "artifact_id": "understanding_json",
            "filename": json_path.name,
            "file_path": str(json_path),
            "artifact_type": "drawing_understanding",
        }
        meta["artifacts"]["understanding_txt"] = {
            "artifact_id": "understanding_txt",
            "filename": txt_path.name,
            "file_path": str(txt_path),
            "artifact_type": "drawing_understanding_text",
        }
        if understanding.normalized_png_path:
            png_path = Path(understanding.normalized_png_path)
            meta["artifacts"]["normalized_png"] = {
                "artifact_id": "normalized_png",
                "filename": png_path.name,
                "file_path": str(png_path),
                "artifact_type": "normalized_drawing_png",
            }
        if understanding.feature_graph:
            fg_path = pdir / f"{stem}_feature_graph.json"
            fg_path.write_text(understanding.feature_graph.model_dump_json(indent=2), encoding="utf-8")
            meta["artifacts"]["feature_graph"] = {
                "artifact_id": "feature_graph",
                "filename": fg_path.name,
                "file_path": str(fg_path),
                "artifact_type": "feature_graph_json",
            }
            # Also generate and save the Phase 19A Reconstruction Blueprint
            try:
                from src.drawing.reconstruction_planner import ReconstructionPlanner
                planner = ReconstructionPlanner()
                plan = planner.plan(project_id, understanding.feature_graph)
                plan_path = pdir / f"{stem}_reconstruction_plan.json"
                plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                meta["artifacts"]["reconstruction_plan"] = {
                    "artifact_id": "reconstruction_plan",
                    "filename": plan_path.name,
                    "file_path": str(plan_path),
                    "artifact_type": "reconstruction_plan_json",
                }
            except Exception:
                pass
        self._save_meta(project_id, meta)
        return json_path

    def get_understanding(self, project_id: str) -> DrawingUnderstanding:
        """Load the saved DrawingUnderstanding for a project."""
        meta = self._load_meta(project_id)
        artifact = meta.get("artifacts", {}).get("understanding_json")
        if not artifact:
            raise FileNotFoundError(
                f"No drawing understanding found for project '{project_id}'. "
                "Run /analyze first."
            )
        json_path = Path(artifact["file_path"])
        if not json_path.exists():
            raise FileNotFoundError(f"Understanding file missing on disk: {json_path}")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return DrawingUnderstanding.model_validate(data)

    def get_reconstruction_plan(self, project_id: str) -> Any:
        """Load or generate the Phase 19A/19A.2 ParametricReconstructionPlan and Evidence Audit."""
        from src.drawing.reconstruction_schemas import ParametricReconstructionPlan
        from src.drawing.reconstruction_planner import ReconstructionPlanner
        from src.drawing.reconstruction_auditor import ReconstructionAuditor

        meta = self._load_meta(project_id)
        u = self.get_understanding(project_id)
        if not u.feature_graph:
            try:
                from src.drawing.feature_synthesizer import FeatureSynthesizer
                views_list = (u.claude_result.views if u.claude_result else []) or (u.gemini_result.views if u.gemini_result else [])
                views_map = {v.view_id: v.view_type for v in views_list}
                dims = u.all_dimensions_combined
                all_entities = (u.claude_result.entities if u.claude_result else []) + (u.gemini_result.entities if u.gemini_result else [])
                c_dims = u.claude_result.dimensions if u.claude_result else []
                g_dims = u.gemini_result.dimensions if u.gemini_result else []
                u.feature_graph = FeatureSynthesizer().synthesize(
                    dims,
                    views_map,
                    entities=all_entities,
                    claude_dims=c_dims,
                    gemini_dims=g_dims,
                )
                self.save_understanding(project_id, u)
            except Exception:
                from src.drawing.schemas import FeatureGraph
                u.feature_graph = FeatureGraph(features=[])

        planner = ReconstructionPlanner()
        plan = planner.plan(project_id, u.feature_graph)

        auditor = ReconstructionAuditor()
        audit = auditor.audit_plan(project_id, plan, u.feature_graph)
        report_md = auditor.generate_markdown_report(audit)

        pdir = self._project_dir(project_id)
        stem = Path(meta["filename"]).stem
        plan_path = pdir / f"{stem}_reconstruction_plan.json"
        audit_path = pdir / f"{stem}_reconstruction_evidence_audit.json"
        report_path = pdir / f"{stem}_reconstruction_evidence_report.md"

        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        audit_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
        report_path.write_text(report_md, encoding="utf-8")

        meta.setdefault("artifacts", {})
        meta["artifacts"]["reconstruction_plan"] = {
            "artifact_id": "reconstruction_plan",
            "filename": plan_path.name,
            "file_path": str(plan_path),
            "artifact_type": "reconstruction_plan_json",
        }
        meta["artifacts"]["reconstruction_evidence_audit"] = {
            "artifact_id": "reconstruction_evidence_audit",
            "filename": audit_path.name,
            "file_path": str(audit_path),
            "artifact_type": "evidence_audit_json",
        }
        meta["artifacts"]["reconstruction_evidence_report"] = {
            "artifact_id": "reconstruction_evidence_report",
            "filename": report_path.name,
            "file_path": str(report_path),
            "artifact_type": "evidence_report_markdown",
        }

        if getattr(plan, "debug_trace", None):
            trace_path = pdir / f"{stem}_reconstruction_debug_trace.json"
            trace_path.write_text(plan.debug_trace.model_dump_json(indent=2), encoding="utf-8")
            meta["artifacts"]["reconstruction_debug_trace"] = {
                "artifact_id": "reconstruction_debug_trace",
                "filename": trace_path.name,
                "file_path": str(trace_path),
                "artifact_type": "debug_trace_json",
            }

        self._save_meta(project_id, meta)
        return plan

    def get_artifact_path(self, project_id: str, artifact_id: str) -> Path:
        """Resolve artifact to filesystem path."""
        meta = self._load_meta(project_id)
        artifacts = meta.get("artifacts", {})
        if artifact_id in artifacts:
            p = Path(artifacts[artifact_id]["file_path"])
            if p.exists():
                return p

        # Disk fallback for well-known artifact types
        pdir = self._project_dir(project_id)
        stem = Path(meta["filename"]).stem
        ext = Path(meta["filename"]).suffix.lower()

        fallbacks: dict[str, list[Path]] = {
            "normalized_png": [pdir / f"{stem}_normalized.png"],
            "source_drawing": [pdir / f"{stem}_source{ext}"],
            "understanding_json": [pdir / f"{stem}_drawing_understanding.json"],
            "understanding_txt": [pdir / f"{stem}_drawing_understanding.txt"],
            "feature_graph": [pdir / f"{stem}_feature_graph.json"],
            "reconstruction_plan": [pdir / f"{stem}_reconstruction_plan.json"],
            "gemini_cad_plan": [pdir / "gemini_cad_reconstruction_plan.json"],
            "reconstructed_step": [pdir / "reconstructed_step.step"],
            "reconstructed_mesh": [pdir / "reconstructed_mesh.json"],
            "reconstruction_evidence_audit": [pdir / f"{stem}_reconstruction_evidence_audit.json"],
            "reconstruction_evidence_report": [pdir / f"{stem}_reconstruction_evidence_report.md"],
            "reconstruction_debug_trace": [pdir / f"{stem}_reconstruction_debug_trace.json", pdir / "reconstruction_debug_trace.json"],
            "manifest_claude": [pdir / f"{stem}_multimodal_request_claude.json"],
            "manifest_gemini": [pdir / f"{stem}_multimodal_request_gemini.json"],
        }
        for cand in fallbacks.get(artifact_id, []):
            if cand.exists():
                return cand

        raise FileNotFoundError(
            f"Artifact '{artifact_id}' not found for drawing project '{project_id}'."
        )

    def execute_custom_cad_plan(self, project_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a structured CAD reconstruction plan using controlled FreeCAD / OCCT tools."""
        from src.drawing.cad_reconstructor import CADReconstructor
        from src.drawing.reconstruction_schemas import CADReconstructionPlan

        pdir = self._project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        plan = CADReconstructionPlan.model_validate(plan_data)

        # Save plan to workspace
        plan_path = pdir / "gemini_cad_reconstruction_plan.json"
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

        reconstructor = CADReconstructor(workspace_root=_WORKSPACE_ROOT)
        mesh_data = reconstructor.reconstruct_from_plan(project_id, plan)

        meta = self._load_meta(project_id)
        meta["artifacts"]["gemini_cad_plan"] = {
            "artifact_id": "gemini_cad_plan",
            "filename": "gemini_cad_reconstruction_plan.json",
            "file_path": str(plan_path),
            "artifact_type": "gemini_cad_plan_json",
        }
        meta["artifacts"]["reconstructed_step"] = {
            "artifact_id": "reconstructed_step",
            "filename": "reconstructed_step.step",
            "file_path": str(pdir / "reconstructed_step.step"),
            "artifact_type": "step_model",
        }
        meta["artifacts"]["reconstructed_mesh"] = {
            "artifact_id": "reconstructed_mesh",
            "filename": "reconstructed_mesh.json",
            "file_path": str(pdir / "reconstructed_mesh.json"),
            "artifact_type": "mesh_json",
        }
        self._save_meta(project_id, meta)
        return mesh_data

    def gemini_reconstruct_cad(self, project_id: str) -> Dict[str, Any]:
        """Invoke Gemini Vision CAD Brain to interpret drawing and execute controlled CAD primitives."""
        from src.drawing.gemini_cad_reconstructor import GeminiCADReconstructionEngine

        pdir = self._project_dir(project_id)
        meta = self._load_meta(project_id)
        png_path = self.get_artifact_path(project_id, "normalized_png")

        engine = GeminiCADReconstructionEngine(workspace_root=_WORKSPACE_ROOT)
        plan = engine.generate_reconstruction_plan(project_id, png_path, output_dir=pdir)
        result = engine.execute_and_export(project_id, plan, output_dir=pdir)

        meta["artifacts"]["gemini_cad_plan"] = {
            "artifact_id": "gemini_cad_plan",
            "filename": "gemini_cad_reconstruction_plan.json",
            "file_path": str(pdir / "gemini_cad_reconstruction_plan.json"),
            "artifact_type": "gemini_cad_plan_json",
        }
        meta["artifacts"]["reconstructed_step"] = {
            "artifact_id": "reconstructed_step",
            "filename": "reconstructed_step.step",
            "file_path": result["step_path"],
            "artifact_type": "step_model",
        }
        meta["artifacts"]["reconstructed_mesh"] = {
            "artifact_id": "reconstructed_mesh",
            "filename": "reconstructed_mesh.json",
            "file_path": result["mesh_file"],
            "artifact_type": "mesh_json",
        }
        self._save_meta(project_id, meta)
        return result

    def get_status_response(self, project_id: str) -> DrawingProjectStatusResponse:
        meta = self._load_meta(project_id)
        return DrawingProjectStatusResponse(
            project_id=meta["project_id"],
            filename=meta["filename"],
            status=meta["status"],
            created_at=meta["created_at"],
            updated_at=meta["updated_at"],
            sha256=meta.get("sha256", ""),
            file_size_bytes=meta.get("file_size_bytes", 0),
            analysis_complete=meta.get("analysis_complete", False),
            artifacts=meta.get("artifacts", {}),
            error_message=meta.get("error_message"),
        )

    @staticmethod
    def _build_summary(u: DrawingUnderstanding) -> str:
        lines = [
            "=" * 60,
            "PHASE 17 — DRAWING UNDERSTANDING SUMMARY",
            "=" * 60,
            f"Project ID : {u.project_id}",
            f"Filename   : {u.source.filename}",
            f"MIME       : {u.source.mime_type}",
            f"SHA-256    : {u.source.sha256}",
            f"Timestamp  : {u.understanding_timestamp}",
            "",
        ]
        if u.claude_result:
            c = u.claude_result
            lines += [
                f"CLAUDE ({c.model})",
                f"  Views      : {len(c.views)}",
                f"  Dimensions : {len(c.dimensions)}",
                f"  Entities   : {len(c.entities)}",
            ]
            for d in c.dimensions[:10]:
                lines.append(f"    {d.dimension_id}: '{d.raw_text}' → {d.normalized_value} {d.unit or ''}")
            if len(c.dimensions) > 10:
                lines.append(f"    ... and {len(c.dimensions) - 10} more")
            lines.append("")

        if u.gemini_result:
            g = u.gemini_result
            lines += [
                f"GEMINI ({g.model})",
                f"  Views      : {len(g.views)}",
                f"  Dimensions : {len(g.dimensions)}",
                f"  Entities   : {len(g.entities)}",
            ]
            for d in g.dimensions[:10]:
                lines.append(f"    {d.dimension_id}: '{d.raw_text}' → {d.normalized_value} {d.unit or ''}")
            if len(g.dimensions) > 10:
                lines.append(f"    ... and {len(g.dimensions) - 10} more")
            lines.append("")

        if u.consensus:
            co = u.consensus
            lines += [
                "CONSENSUS",
                f"  Agreed dims    : {co.total_agreed}",
                f"  Unresolved     : {co.total_unresolved}",
                f"  Disagreed/Solo : {co.total_disagreed}",
                f"  Claude only    : {len(co.claude_only_dimensions)}",
                f"  Gemini only    : {len(co.gemini_only_dimensions)}",
            ]

        lines += [
            "",
            f"VALIDATION: {'PASSED' if u.validation_passed else 'FAILED'} "
            f"({len(u.validation_errors)} issues)",
            "=" * 60,
        ]
        return "\n".join(lines)
