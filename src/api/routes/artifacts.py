"""Artifact download route."""
from __future__ import annotations

import mimetypes
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from src.api.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Artifacts"])
project_service = ProjectService()


@router.get(
    "/{project_id}/artifacts/{artifact_id}",
    summary="Download Generated CAD Artifact",
)
def download_artifact(project_id: str, artifact_id: str, force: bool = False, t: Optional[str] = None):
    """Securely streams the requested artifact file (FCStd, SVG, DXF, JSON, TXT) to the client."""
    try:
        from src.api.services.drawing_service import DrawingService
        ds = DrawingService(project_service)

        if artifact_id == "industrial_drawing_svg":
            art_path = ds.generate_industrial_sheet(project_id, force=force)
        elif artifact_id == "drawing_svg" and force:
            res = ds.generate_standard_drawing(project_id)
            art_path = project_service.get_artifact_path(project_id, "drawing_svg")
        else:
            try:
                art_path = project_service.get_artifact_path(project_id, artifact_id)
            except FileNotFoundError:
                if artifact_id == "drawing_svg":
                    res = ds.generate_standard_drawing(project_id)
                    art_path = project_service.get_artifact_path(project_id, "drawing_svg")
                else:
                    raise

        media_type, _ = mimetypes.guess_type(str(art_path))
        if media_type is None:
            if art_path.suffix.lower() == ".fcstd":
                media_type = "application/octet-stream"
            elif art_path.suffix.lower() == ".dxf":
                media_type = "image/vnd.dxf"
            elif art_path.suffix.lower() == ".svg":
                media_type = "image/svg+xml"
            else:
                media_type = "application/octet-stream"

        return FileResponse(
            path=str(art_path),
            media_type=media_type,
            filename=art_path.name,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
