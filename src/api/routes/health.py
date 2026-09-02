"""Health check router."""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Service Health Check")
def get_health():
    """Returns the operational status of the CAD Intelligence API service."""
    return {
        "status": "ok",
        "service": "cad-intelligence-api",
        "version": "1.0.0",
    }
