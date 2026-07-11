from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import HealthPayload
from app.security import get_current_user
import json

router = APIRouter()

@router.post("/webhook/health")
def receive_health(payload: HealthPayload, db: Session = Depends(get_db),
                   user: dict = Depends(get_current_user)):
    """Nightly push from a user's iPhone Shortcut (X-Api-Token identifies whose
    phone). Idempotent upsert on (user, date)."""
    db.execute(text("""
        INSERT INTO health_metrics (user_id, date, steps, active_kcal, workouts, raw_payload)
        VALUES (:u, :d, :s, :k, CAST(:w AS jsonb), CAST(:r AS jsonb))
        ON CONFLICT (user_id, date) DO UPDATE
          SET steps = EXCLUDED.steps,
              active_kcal = EXCLUDED.active_kcal,
              workouts = EXCLUDED.workouts,
              raw_payload = EXCLUDED.raw_payload,
              received_at = now()
    """), {"u": user["id"], "d": payload.date, "s": payload.steps,
           "k": payload.active_kcal,
           "w": json.dumps([w.model_dump() for w in payload.workouts]),
           "r": payload.model_dump_json()})
    db.commit()
    return {"ok": True, "date": str(payload.date), "user": user["name"]}
