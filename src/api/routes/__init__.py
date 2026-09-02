"""Routes package."""
from src.api.routes.health import router as health_router
from src.api.routes.projects import router as projects_router
from src.api.routes.analysis import router as analysis_router
from src.api.routes.features import router as features_router
from src.api.routes.dimensions import router as dimensions_router
from src.api.routes.drawings import router as drawings_router
from src.api.routes.artifacts import router as artifacts_router
from src.api.routes.ai_review import router as ai_review_router
from src.api.routes.issues import router as issues_router
from src.api.routes.drawing_projects import router as drawing_projects_router
from src.api.routes.mold_analysis import router as mold_analysis_router

__all__ = [
    "health_router",
    "projects_router",
    "analysis_router",
    "features_router",
    "dimensions_router",
    "drawings_router",
    "artifacts_router",
    "ai_review_router",
    "issues_router",
    "drawing_projects_router",
    "mold_analysis_router",
]
