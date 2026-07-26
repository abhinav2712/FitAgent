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
    """Push from a user's iPhone Shortcut (X-Api-Token identifies whose phone).
    Partial upsert on (user, date): for the cumulative daily counters (steps,
    active_kcal) an incoming value that is absent OR 0 means "this Shortcut has
    no reading for that field" and leaves the stored value untouched (NULLIF +
    COALESCE). That's what lets a steps-only Shortcut and a calories-only
    Shortcut coexist — the calories one sends steps=0, which no longer wipes the
    real step count. Still idempotent (re-sending the same payload is a no-op).
    An explicit non-zero always wins, and the first write of the day can seed 0."""
    workouts = None if payload.workouts is None else \
        json.dumps([w.model_dump() for w in payload.workouts])
    dash = lambda v: "—" if v is None else v
    print(f"[webhook] {user['name']} {payload.date}: steps={dash(payload.steps)}, "
          f"active_kcal={dash(payload.active_kcal)}, "
          f"workouts={0 if payload.workouts is None else len(payload.workouts)}"
          + "".join(f" [{w.type}: {w.distance_km or '?'}km {w.duration_min or '?'}min]"
                    for w in (payload.workouts or [])))
    db.execute(text("""
        INSERT INTO health_metrics (user_id, date, steps, active_kcal, workouts, raw_payload)
        VALUES (:u, :d, :s, :k, CAST(:w AS jsonb), CAST(:r AS jsonb))
        ON CONFLICT (user_id, date) DO UPDATE
          SET steps       = COALESCE(NULLIF(EXCLUDED.steps, 0),       health_metrics.steps),
              active_kcal = COALESCE(NULLIF(EXCLUDED.active_kcal, 0), health_metrics.active_kcal),
              workouts    = COALESCE(EXCLUDED.workouts,               health_metrics.workouts),
              raw_payload = EXCLUDED.raw_payload,
              received_at = now()
    """), {"u": user["id"], "d": payload.date, "s": payload.steps,
           "k": payload.active_kcal, "w": workouts,
           "r": payload.model_dump_json()})
    db.commit()
    return {"ok": True, "date": str(payload.date), "user": user["name"]}
