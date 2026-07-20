from datetime import date as Date
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.security import get_current_user

router = APIRouter()

@router.get("/recommendations/{d}")
def recommendations_for_day(d: Date, db: Session = Depends(get_db),
                            user: dict = Depends(get_current_user)):
    """Latest agent food recommendations for a day, per kind — feeds the
    tracker's Swiggy-picks and Instamart cards. Macros inside items are
    agent estimates ('est.'). {"food": {...}|null, "instamart": {...}|null}"""
    out = {"food": None, "instamart": None}
    key_by_kind = {"swiggy_food": "food", "instamart_snack": "instamart"}
    for kind, key in key_by_kind.items():
        row = db.execute(text("""
            SELECT items, remaining_kcal, remaining_protein, created_at
            FROM recommendations WHERE user_id = :u AND date = :d AND kind = :k
            ORDER BY id DESC LIMIT 1
        """), {"u": user["id"], "d": d, "k": kind}).mappings().first()
        if row:
            out[key] = dict(row)
    return out
