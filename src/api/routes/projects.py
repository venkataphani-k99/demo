"""Project creation and status routes."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.api.schemas import ProjectCreateResponse, ProjectStatusResponse
from src.api.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])
project_service = ProjectService()


@router.post(
    "",
    response_model=ProjectCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload STEP CAD File and Create Project",
)
async def upload_step_file(file: UploadFile = File(...)):
    """Uploads a `.step` or `.stp` CAD model, creates an isolated workspace, and returns project metadata."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    suffix = file.filename.lower()
    if not (suffix.endswith(".step") or suffix.endswith(".stp")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .step and .stp files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        meta = project_service.create_project(file.filename, content)
        return ProjectCreateResponse(
            project_id=meta["project_id"],
            filename=meta["filename"],
            status=meta["status"],
            created_at=meta["created_at"],
            sha256_hash=meta.get("sha256_hash"),
            file_size_bytes=meta.get("file_size_bytes"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize project workspace")


@router.get(
    "/{project_id}",
    response_model=ProjectStatusResponse,
    summary="Get Project Status and Available Artifacts",
)
def get_project_status(project_id: str):
    """Retrieves current processing status, metadata, and all registered downloadable artifacts for a project."""
    try:
        return project_service.get_status_response(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
