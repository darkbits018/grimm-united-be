from fastapi import APIRouter
from app.stats import get_stats

router = APIRouter()


@router.get("/")
def read_root():
    return {"status": "Grimm United Backend is running"}


@router.get("/api/stats")
def get_interest_stats():
    return get_stats()
