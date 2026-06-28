from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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

    # -----------------------------------------------------------------------
    # Global Exception Handlers
    # Guarantee a uniform {"detail": "..."} JSON response shape for all
    # unhandled errors, regardless of where in the stack they originate.
    # -----------------------------------------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Returns 422 with Pydantic validation details in FastAPI's default format."""
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """Returns 500 for any uncaught database-layer failure."""
        return JSONResponse(
            status_code=500,
            content={"detail": "A database error occurred. Please try again later."},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all safety net — returns 500 for any unhandled runtime error."""
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected internal server error occurred."},
        )

    return app



app = create_app()