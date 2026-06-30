"""FastAPI application that serves the upload API and the frontend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .endpoints.upload import router as upload_router
from .endpoints.ingest import router as ingest_router
from .endpoints.instances import router as instances_router

# After `npm run build`, the frontend lives in src/frontend/dist
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SCEPA Database Builder",
        description="API for uploading and managing documents in the SCEPA knowledge platform.",
        version="0.1.0",
    )

    app.include_router(upload_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(instances_router, prefix="/api/v1")

    # Serve the built React frontend as static files at the root
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app()
