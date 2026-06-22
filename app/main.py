from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db , engine, Base
from app.models.asset import Asset
from app.models.relationship import AssetRelationship
from app.routers.assets import router as assets_router

def create_app() -> FastAPI:

  Base.metadata.create_all(bind=engine)

  app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
  )

  app.include_router(assets_router)

  @app.get("/health")
  async def health(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "connected",
                "app_name": settings.APP_NAME
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Database connection failed: {str(e)}"
            )

  return app

app = create_app()