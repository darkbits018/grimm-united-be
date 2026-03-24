from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.models import Base
from app.config import settings

engine = None
SessionLocal = None

if settings and settings.DATABASE_URL:
    try:
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        print("Success: Connected to PostgreSQL database")
    except Exception as e:
        print(f"Warning: Could not connect to database. Error: {e}")


def get_db():
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
