"""Drawing Service Layer: Bridges FastAPI endpoints with TechDraw generation pipelines."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional

from src.api.schemas import DrawingArtifactSchema, DrawingResponse
from src.api.services.project_service import ProjectService
from src.cad.freecad_env import get_freecad_python


FREECAD_PYTHON = get_freecad_python()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class DrawingService:
    """Invokes standard TechDraw generation and complete dimensioned drawing pipelines with concurrency locking."""

    _global_lock = threading.Lock()
    _project_locks: Dict[str, threading.Lock] = {}

    def __init__(self, project_service: Optional[ProjectService] = None):
        self.project_service = project_service or ProjectService()

    def _get_project_lock(self, project_id: str) -> threading.Lock:
        with self._global_lock:
            if project_id not in self._project_locks:
                self._project_locks[project_id] = threading.Lock()
            return self._project_locks[project_id]

    def generate_standard_drawing(
        self,
        project_id: str,
        projection: str = "third-angle",
        template: str = "A3_Landscape_blank.svg",
        scale: float = 0.0,
    ) -> DrawingResponse:
        """Generate standard 5-view orthographic drawing (Phase 6) protected by concurrency mutex."""
        lock = self._get_project_lock(project_id)
        with lock:
            meta = self.project_service.get_project_metadata(project_id)
            step_file = Path(meta["step_file"])
            pdir = step_file.parent

            self.project_service.update_project_status(project_id, "drawing_generating")

            try:
                base_name = step_file.stem
                fcstd_path = pdir / f"{base_name}_drawing.FCStd"
                svg_path = pdir / f"{base_name}_drawing.svg"
                dxf_path = pdir / f"{base_name}_drawing.dxf"

                if not svg_path.exists():
                    proj_arg = "third" if "third" in projection.lower() else "first"
                    cmd = [
                        FREECAD_PYTHON,
                        "-m", "src.main",
                        "draw",
                        str(step_file),
                        "--output-dir", str(pdir),
                        "--projection", proj_arg,
                        "--scale", str(scale),
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
                    if res.returncode != 0:
                        raise RuntimeError(f"Drawing generation failed: {res.stderr or res.stdout}")

                artifacts = []
                if fcstd_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "drawing_fcstd", "fcstd", fcstd_path))
                if svg_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "drawing_svg", "svg", svg_path))
                if dxf_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "drawing_dxf", "dxf", dxf_path))

                self.project_service.update_project_status(project_id, "drawing_generated")

                return DrawingResponse(
                    project_id=project_id,
                    status="completed",
                    drawing_type="standard_5view",
                    artifacts=artifacts,
                )

            except Exception as e:
                self.project_service.update_project_status(project_id, "failed", str(e))
                raise

    def generate_dimensioned_drawing(
        self,
        project_id: str,
    ) -> DrawingResponse:
        """Generate complete dimensioned TechDraw drawing (Phase 9A) protected by concurrency mutex."""
        lock = self._get_project_lock(project_id)
        with lock:
            meta = self.project_service.get_project_metadata(project_id)
            step_file = Path(meta["step_file"])
            pdir = step_file.parent

            self.project_service.update_project_status(project_id, "dimensioning")

            try:
                base_name = step_file.stem
                fcstd_path = pdir / f"{base_name}_complete_dimensioned.FCStd"
                if not fcstd_path.exists():
                    fcstd_path = pdir / f"{base_name}_drawing.FCStd"
                json_path = pdir / f"{base_name}_complete_dimensions.json"
                txt_path = pdir / f"{base_name}_complete_dimensions.txt"
                svg_path = pdir / f"{base_name}_complete_dimensioned.svg"
                if not svg_path.exists():
                    svg_path = pdir / f"{base_name}_drawing.svg"
                dxf_path = pdir / f"{base_name}_drawing.dxf"

                # Only run FreeCAD generation if drawing SVG / FCStd does not already exist
                if not (svg_path.exists() and json_path.exists()):
                    cmd = [
                        FREECAD_PYTHON,
                        "-m", "src.main",
                        "complete-dimensions",
                        str(step_file),
                        "--output-dir", str(pdir),
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
                    if res.returncode != 0:
                        raise RuntimeError(f"Dimensioned drawing generation failed: {res.stderr or res.stdout}")

                    if not fcstd_path.exists():
                        fcstd_path = pdir / f"{base_name}_drawing.FCStd"
                    if not svg_path.exists():
                        svg_path = pdir / f"{base_name}_drawing.svg"

                artifacts = []
                if fcstd_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "dimensioned_fcstd", "fcstd", fcstd_path))
                if svg_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "drawing_svg", "svg", svg_path))
                if dxf_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "drawing_dxf", "dxf", dxf_path))
                if json_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "dimensions_json", "json", json_path))
                if txt_path.exists():
                    artifacts.append(self.project_service.register_artifact(project_id, "dimensions_report", "txt", txt_path))

                self.project_service.update_project_status(project_id, "completed")

                return DrawingResponse(
                    project_id=project_id,
                    status="completed",
                    drawing_type="complete_dimensioned",
                    artifacts=artifacts,
                )

            except Exception as e:
                self.project_service.update_project_status(project_id, "failed", str(e))
                raise
