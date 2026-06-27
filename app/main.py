from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db
from app.routers.assets_router import router as assets_router
from app.routers.relationships_router import router as relationships_router
from app.routers.auth_router import router as auth_router


def create_app() -> FastAPI:
    """Application factory — wires together all routers and middleware.

    NOTE: Base.metadata.create_all() has been intentionally removed.
    Schema management is now exclusively handled by Alembic migrations.
    Run `alembic upgrade head` before starting the server.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="1.0.0",
        description="DarkAtlas — Attack Surface Management Platform",
    )

    app.include_router(auth_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)

    @app.get("/health", tags=["Health"])
    async def health(db: Session = Depends(get_db)):
        """Liveness probe — verifies application and database connectivity."""
        try:
            db.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "connected",
                "app_name": settings.APP_NAME,
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Database connection failed: {str(e)}",
            )

    return app


app = create_app()