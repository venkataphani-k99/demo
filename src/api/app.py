"""FastAPI application entrypoint for CAD Intelligence and Automation Service."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import (
    health_router,
    projects_router,
    analysis_router,
    features_router,
    dimensions_router,
    drawings_router,
    artifacts_router,
    ai_review_router,
    issues_router,
    drawing_projects_router,
    reconstruction_router,
    mold_analysis_router,
)


def create_app() -> FastAPI:
    """Factory creating configured FastAPI application."""
    app = FastAPI(
        title="CAD Intelligence Platform API",
        description=(
            "HTTP REST API service providing 3D STEP analysis, B-Rep topology inspection, "
            "feature recognition, exact geometric measurement, TechDraw 2D orthographic drawing generation, "
            "and deterministic engineering dimensioning powered by FreeCAD / OpenCASCADE."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS for local Next.js development
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API v1 routers
    api_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_prefix)
    app.include_router(projects_router, prefix=api_prefix)
    app.include_router(analysis_router, prefix=api_prefix)
    app.include_router(features_router, prefix=api_prefix)
    app.include_router(dimensions_router, prefix=api_prefix)
    app.include_router(drawings_router, prefix=api_prefix)
    app.include_router(artifacts_router, prefix=api_prefix)
    app.include_router(ai_review_router, prefix=api_prefix)
    app.include_router(issues_router, prefix=api_prefix)
    app.include_router(drawing_projects_router, prefix=api_prefix)
    app.include_router(reconstruction_router, prefix=api_prefix)
    app.include_router(mold_analysis_router, prefix=api_prefix)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["src"],
        reload_excludes=["workspaces", "workspaces/*", "*.STEP", "*.step", "*.FCStd", "*.json", "*_build123d.py"],
    )
