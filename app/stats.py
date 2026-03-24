import os
import json

COUNTER_FILE = "stats.json"


def get_stats() -> dict:
    from app.database import SessionLocal
    from app.models import Submission
    try:
        db = SessionLocal()
        count = db.query(Submission).count()
        db.close()
        return {"interest_count": count}
    except Exception:
        # fallback to file if DB unavailable
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, "r") as f:
                return json.load(f)
        return {"interest_count": 0}


def update_stats() -> dict:
    # no-op — count is now live from DB
    return get_stats()


async def simulate_growth():
    pass
