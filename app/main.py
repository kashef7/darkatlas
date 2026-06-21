from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db


def create_app() -> FastAPI:
  app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
  )

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