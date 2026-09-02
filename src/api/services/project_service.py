"""Project workspace and lifecycle management service."""
from __future__ import annotations

import datetime
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.api.schemas import DrawingArtifactSchema, ProjectStatusResponse


# Root directory for project workspaces
WORKSPACE_ROOT = Path("workspaces").resolve()


class ProjectService:
    """Manages project workspaces, uploaded STEP files, and generated artifacts."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.root = (workspace_root or WORKSPACE_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_id: str) -> Path:
        """Securely get project directory without path traversal."""
        # Sanitize project_id to alphanumeric + hyphen only
        if not re.match(r"^[a-zA-Z0-9_\-]+$", project_id):
            raise ValueError("Invalid project_id format")
        pdir = (self.root / project_id).resolve()
        # Verify it is strictly under self.root
        if not str(pdir).startswith(str(self.root)):
            raise ValueError("Path traversal detected")
        return pdir

    def find_project_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """Locate any existing project workspace containing an identical SHA-256 hash."""
        if not self.root.exists():
            return None
        for pdir in self.root.iterdir():
            if not pdir.is_dir():
                continue
            meta_file = pdir / "project.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("sha256_hash") == sha256_hash:
                        # Verify the step file exists
                        step_f = Path(meta.get("step_file", ""))
                        if step_f.exists():
                            return meta
                except Exception:
                    continue
        return None

    def create_project(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Create or immediately reuse an existing analyzed workspace based on SHA-256 content hash."""
        # Validate extension
        suffix = Path(filename).suffix.lower()
        if suffix not in (".step", ".stp"):
            raise ValueError(f"Unsupported file extension '{suffix}'. Only .step and .stp are accepted.")

        import hashlib
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Check if an identical CAD model was already uploaded & processed
        existing = self.find_project_by_hash(sha256_hash)
        if existing:
            # Re-register any on-disk artifacts and return instantly
            return existing

        project_id = str(uuid.uuid4())
        pdir = self._get_project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", Path(filename).name)
        step_path = pdir / safe_name
        step_path.write_bytes(content)

        file_size_bytes = len(content)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        meta = {
            "project_id": project_id,
            "filename": safe_name,
            "step_file": str(step_path),
            "status": "uploaded",
            "sha256_hash": sha256_hash,
            "file_size_bytes": file_size_bytes,
            "created_at": now_iso,
            "updated_at": now_iso,
            "artifacts": {},
            "error_message": None,
        }
        self._save_metadata(project_id, meta)
        return meta

    def get_project_metadata(self, project_id: str) -> Dict[str, Any]:
        """Retrieve project metadata with concurrency protection."""
        pdir = self._get_project_dir(project_id)
        if not pdir.exists():
            raise FileNotFoundError(f"Project '{project_id}' not found")
        meta_file = pdir / "project.json"
        if not meta_file.exists():
            raise FileNotFoundError(f"Metadata for project '{project_id}' not found")

        for _ in range(5):
            try:
                content = meta_file.read_text(encoding="utf-8").strip()
                if content:
                    return json.loads(content)
            except Exception:
                pass
            time.sleep(0.05)

        content = meta_file.read_text(encoding="utf-8")
        return json.loads(content)

    def update_project_status(
        self,
        project_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update project status and timestamp."""
        meta = self.get_project_metadata(project_id)
        meta["status"] = status
        meta["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if error_message:
            meta["error_message"] = error_message
        self._save_metadata(project_id, meta)

    def register_artifact(
        self,
        project_id: str,
        artifact_id: str,
        artifact_type: str,
        file_path: Path,
    ) -> DrawingArtifactSchema:
        """Register a generated artifact with the project."""
        meta = self.get_project_metadata(project_id)
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Artifact file '{file_path}' does not exist on disk")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        art_schema = DrawingArtifactSchema(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            filename=file_path.name,
            size_bytes=file_path.stat().st_size,
            download_url=f"/api/v1/projects/{project_id}/artifacts/{artifact_id}",
        )

        if "artifacts" not in meta:
            meta["artifacts"] = {}
        meta["artifacts"][artifact_id] = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "filename": file_path.name,
            "file_path": str(file_path),
            "size_bytes": file_path.stat().st_size,
            "download_url": art_schema.download_url,
            "registered_at": now_iso,
        }
        meta["updated_at"] = now_iso
        self._save_metadata(project_id, meta)
        return art_schema

    def get_artifact_path(self, project_id: str, artifact_id: str) -> Path:
        """Retrieve the filesystem path for a registered artifact."""
        meta = self.get_project_metadata(project_id)
        artifacts = meta.get("artifacts", {})
        if artifact_id in artifacts:
            art_info = artifacts[artifact_id]
            art_path = Path(art_info["file_path"])
            if art_path.exists():
                return art_path

        # Robust fallback: check disk directory directly for standard artifact types
        pdir = self._get_project_dir(project_id)
        base_name = Path(meta["filename"]).stem
        fallbacks = {
            "drawing_svg": [pdir / f"{base_name}_complete_dimensioned.svg", pdir / f"{base_name}_drawing.svg"],
            "drawing_dxf": [pdir / f"{base_name}_drawing.dxf", pdir / f"{base_name}_complete_dimensioned.dxf"],
            "dimensioned_fcstd": [pdir / f"{base_name}_complete_dimensioned.FCStd", pdir / f"{base_name}_drawing.FCStd"],
            "drawing_fcstd": [pdir / f"{base_name}_drawing.FCStd", pdir / f"{base_name}_complete_dimensioned.FCStd"],
            "analysis_json": [pdir / f"{base_name}_analysis.json"],
            "dimensions_json": [pdir / f"{base_name}_complete_dimensions.json", pdir / f"{base_name}_dimensions.json"],
        }
        if artifact_id in fallbacks:
            for cand in fallbacks[artifact_id]:
                if cand.exists():
                    return cand

        raise FileNotFoundError(f"Artifact '{artifact_id}' not found on disk for project '{project_id}'")

    def get_status_response(self, project_id: str) -> ProjectStatusResponse:
        """Get structured status response."""
        meta = self.get_project_metadata(project_id)
        artifacts = [
            DrawingArtifactSchema(
                artifact_id=a["artifact_id"],
                artifact_type=a["artifact_type"],
                filename=a["filename"],
                size_bytes=a["size_bytes"],
                download_url=a["download_url"],
            )
            for a in meta.get("artifacts", {}).values()
        ]
        return ProjectStatusResponse(
            project_id=meta["project_id"],
            filename=meta["filename"],
            status=meta["status"],
            created_at=meta["created_at"],
            updated_at=meta["updated_at"],
            sha256_hash=meta.get("sha256_hash"),
            file_size_bytes=meta.get("file_size_bytes"),
            artifacts=artifacts,
            error_message=meta.get("error_message"),
        )

    def _save_metadata(self, project_id: str, meta: Dict[str, Any]) -> None:
        pdir = self._get_project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        meta_file = pdir / "project.json"
        tmp_file = pdir / f"project.json.{uuid.uuid4().hex}.tmp"
        try:
            tmp_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            tmp_file.replace(meta_file)
        except OSError:
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
