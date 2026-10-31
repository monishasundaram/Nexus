from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..config import MODEL_VERSION
from ..database import get_db

router = APIRouter()

@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "model_version": MODEL_VERSION}