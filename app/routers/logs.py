from datetime import date as Date
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import MealLogIn, WeightIn, CommentIn
from app.security import get_current_user

router = APIRouter()

@router.post("/log/meals")
def log_meal(m: MealLogIn, db: Session = Depends(get_db),
             user: dict = Depends(get_current_user)):
    db.execute(text("""
        INSERT INTO meal_logs (user_id, date, meal_id, name, kcal, protein_g, checked)
        VALUES (:user_id, :date, :meal_id, :name, :kcal, :protein_g, :checked)
        ON CONFLICT (user_id, date, meal_id) DO UPDATE
          SET checked = EXCLUDED.checked, kcal = EXCLUDED.kcal,
              protein_g = EXCLUDED.protein_g, name = EXCLUDED.name
    """), {**m.model_dump(), "user_id": user["id"]})
    db.commit()
    return {"ok": True}

@router.put("/log/weight")
def log_weight(w: WeightIn, db: Session = Depends(get_db),
               user: dict = Depends(get_current_user)):
    db.execute(text("""
        INSERT INTO weight_logs (user_id, date, weight_kg) VALUES (:user_id, :date, :weight_kg)
        ON CONFLICT (user_id, date) DO UPDATE SET weight_kg = EXCLUDED.weight_kg
    """), {**w.model_dump(), "user_id": user["id"]})
    db.commit()
    return {"ok": True}

@router.post("/log/comment")
def log_comment(c: CommentIn, db: Session = Depends(get_db),
                user: dict = Depends(get_current_user)):
    """Comments are the agent's inbox — the worker polls unprocessed rows."""
    db.execute(text(
        "INSERT INTO comments (user_id, date, text) VALUES (:user_id, :date, :text)"),
        {**c.model_dump(), "user_id": user["id"]})
    db.commit()
    return {"ok": True, "note": "agent will pick this up within ~5s and stream its reply live"}

@router.get("/log/day/{d}")
def day_log(d: Date, db: Session = Depends(get_db),
            user: dict = Depends(get_current_user)):
    """Everything logged for one day — hydrates the tracker's Today tab
    (includes off-plan rows the agent inserted from comments)."""
    meals = [dict(r) for r in db.execute(text("""
        SELECT meal_id, name, kcal, protein_g, checked FROM meal_logs
        WHERE user_id=:u AND date=:d ORDER BY id
    """), {"u": user["id"], "d": d}).mappings()]
    w = db.execute(text(
        "SELECT weight_kg FROM weight_logs WHERE user_id=:u AND date=:d"),
        {"u": user["id"], "d": d}).first()
    h = db.execute(text(
        "SELECT steps, active_kcal, workouts FROM health_metrics WHERE user_id=:u AND date=:d"),
        {"u": user["id"], "d": d}).mappings().first()
    notes = [r[0] for r in db.execute(text(
        "SELECT note FROM day_notes WHERE user_id=:u AND date=:d ORDER BY id"),
        {"u": user["id"], "d": d})]
    return {"date": str(d), "meals": meals, "weight_kg": float(w[0]) if w else None,
            "health": dict(h) if h else None, "notes": notes}

@router.get("/log/history")
def log_history(days: int = 21, db: Session = Depends(get_db),
                user: dict = Depends(get_current_user)):
    """Per-day checked-meal totals + weight + steps, newest first — Progress tab."""
    out: dict = {}
    for r in db.execute(text("""
        SELECT date, meal_id, kcal, protein_g FROM meal_logs
        WHERE user_id=:u AND checked AND date > current_date - :days
    """), {"u": user["id"], "days": days}).mappings():
        d = out.setdefault(str(r["date"]), {"date": str(r["date"]), "kcal": 0,
                                            "protein_g": 0, "meal_ids": []})
        d["kcal"] += r["kcal"]
        d["protein_g"] += r["protein_g"]
        d["meal_ids"].append(r["meal_id"])
    for date_, w in db.execute(text("""
        SELECT date, weight_kg FROM weight_logs WHERE user_id=:u AND date > current_date - :days
    """), {"u": user["id"], "days": days}):
        out.setdefault(str(date_), {"date": str(date_), "kcal": 0, "protein_g": 0,
                                    "meal_ids": []})["weight_kg"] = float(w)
    for r in db.execute(text("""
        SELECT date, steps, active_kcal FROM health_metrics
        WHERE user_id=:u AND date > current_date - :days
    """), {"u": user["id"], "days": days}).mappings():
        d = out.setdefault(str(r["date"]), {"date": str(r["date"]), "kcal": 0,
                                            "protein_g": 0, "meal_ids": []})
        d["steps"] = r["steps"]
        d["active_kcal"] = r["active_kcal"]
    return sorted(out.values(), key=lambda x: x["date"], reverse=True)

@router.get("/log/chat")
def chat_history(limit: int = 30, db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    """Comment thread with agent replies (via comments.agent_run_id), oldest
    first — feeds the in-app chat panel as the durable/reconciliation source.
    Live progress and token-by-token text arrive first over GET /log/chat/stream
    (agent/chat_stream.py); this is what backfills if that connection was
    missed or the panel wasn't open."""
    rows = db.execute(text("""
        SELECT c.id, c.date, c.text, c.processed, c.created_at,
               r.output_text AS reply
        FROM comments c LEFT JOIN agent_runs r ON r.id = c.agent_run_id
        WHERE c.user_id = :u
        ORDER BY c.id DESC LIMIT :n
    """), {"u": user["id"], "n": limit}).mappings().all()
    return [dict(r) for r in reversed(rows)]
