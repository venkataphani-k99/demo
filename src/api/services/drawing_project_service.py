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
        if hasattr(DrawingUnderstanding, "model_validate"):
            return DrawingUnderstanding.model_validate(data)
        elif hasattr(DrawingUnderstanding, "parse_obj"):
            return DrawingUnderstanding.parse_obj(data)
        return DrawingUnderstanding(**data)

    def get_reconstruction_plan(self, project_id: str) -> Any:
        """Load or generate the Phase 19A/19A.2 ParametricReconstructionPlan and Evidence Audit."""
        from src.drawing.reconstruction_schemas import ParametricReconstructionPlan
        from src.drawing.reconstruction_planner import ReconstructionPlanner
        from src.drawing.reconstruction_auditor import ReconstructionAuditor

        meta = self._load_meta(project_id)
        u = self.get_understanding(project_id)
        if not u.feature_graph:
            raise FileNotFoundError(f"No feature graph available for project '{project_id}'.")

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
        self._save_meta(project_id, meta)
        return plan

    def reconstruct_3d_solid(
        self,
        project_id: str,
        parameter_overrides: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        meta = self._load_meta(project_id)
        plan = self.get_reconstruction_plan(project_id)
        plan_dict = plan.model_dump()

        pdir = self._project_dir(project_id)
        stem = Path(meta["filename"]).stem
        plan_path = pdir / f"{stem}_reconstruction_plan.json"

        # Execute CAD builder in FreeCAD-compatible Python subprocess to guarantee zero DLL conflict
        import subprocess
        from src.cad.freecad_env import get_freecad_python

        py_exe = get_freecad_python()
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        overrides_json = json.dumps(parameter_overrides or {})

        cmd = [
            py_exe,
            "-m", "src.cad.reconstruction_cad_builder",
            str(plan_path),
            "--output-dir", str(pdir),
            "--stem", stem,
            "--overrides", overrides_json,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root_dir))
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"3D CAD Reconstruction engine error: {err_msg}")

        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            from src.cad.reconstruction_cad_builder import ReconstructionCADBuilder
            builder = ReconstructionCADBuilder()
            result = builder.build_solid(
                plan_dict=plan_dict,
                parameter_overrides=parameter_overrides or {},
                output_dir=pdir,
                stem=stem,
            )

        step_path = Path(result["step_file"])
        fcstd_path = Path(result["fcstd_file"])
        mesh_path = Path(result["mesh_file"])

        # Generate standalone build123d Python script
        try:
            from src.drawing.build123d_exporter import Build123dExporter
            b123d_code = Build123dExporter().generate_code(plan_dict, title=stem, parameter_overrides=parameter_overrides)
            b123d_path = pdir / f"{stem}_reconstructed_build123d.py"
            b123d_path.write_text(b123d_code, encoding="utf-8")
        except Exception:
            b123d_path = None

        meta.setdefault("artifacts", {})
        meta["artifacts"]["reconstructed_step"] = {
            "artifact_id": "reconstructed_step",
            "filename": step_path.name,
            "file_path": str(step_path),
            "artifact_type": "step",
        }
        meta["artifacts"]["reconstructed_fcstd"] = {
            "artifact_id": "reconstructed_fcstd",
            "filename": fcstd_path.name,
            "file_path": str(fcstd_path),
            "artifact_type": "fcstd",
        }
        meta["artifacts"]["reconstructed_mesh"] = {
            "artifact_id": "reconstructed_mesh",
            "filename": mesh_path.name,
            "file_path": str(mesh_path),
            "artifact_type": "reconstructed_mesh_json",
        }
        if b123d_path and b123d_path.exists():
            meta["artifacts"]["reconstructed_build123d"] = {
                "artifact_id": "reconstructed_build123d",
                "filename": b123d_path.name,
                "file_path": str(b123d_path),
                "artifact_type": "python_script",
            }
        meta["status"] = "reconstructed"
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_meta(project_id, meta)

        return result

    def get_reconstructed_mesh(self, project_id: str) -> Dict[str, Any]:
        """Load tessellated 3D WebGL mesh for reconstructed CAD solid."""
        meta = self._load_meta(project_id)
        mesh_art = meta.get("artifacts", {}).get("reconstructed_mesh")
        if mesh_art:
            p = Path(mesh_art["file_path"])
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))

        pdir = self._project_dir(project_id)
        stem = Path(meta["filename"]).stem
        cand = pdir / f"{stem}_reconstructed_mesh.json"
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"No reconstructed mesh available for project '{project_id}'. Run 3D reconstruction first.")

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
            "reconstruction_evidence_audit": [pdir / f"{stem}_reconstruction_evidence_audit.json"],
            "reconstruction_evidence_report": [pdir / f"{stem}_reconstruction_evidence_report.md"],
            "reconstructed_step": [pdir / f"{stem}_reconstructed.STEP", pdir / f"{stem}_reconstructed.step"],
            "reconstructed_fcstd": [pdir / f"{stem}_reconstructed.FCStd"],
            "reconstructed_build123d": [pdir / f"{stem}_reconstructed_build123d.py", pdir / "reconstructed_build123d.py"],
            "reconstructed_mesh": [pdir / f"{stem}_reconstructed_mesh.json"],
            "visual_concept_render": [pdir / "visual_concept_render.png", pdir / f"{stem}_visual_concept.png"],
            "manifest_claude": [pdir / f"{stem}_multimodal_request_claude.json"],
            "manifest_gemini": [pdir / f"{stem}_multimodal_request_gemini.json"],
        }
        for cand in fallbacks.get(artifact_id, []):
            if cand.exists():
                return cand

        raise FileNotFoundError(
            f"Artifact '{artifact_id}' not found for drawing project '{project_id}'."
        )

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
