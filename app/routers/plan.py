from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.security import get_current_user

router = APIRouter()

@router.get("/plan/active")
def active_plan(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    row = db.execute(text("""
        SELECT id, plan, created_at FROM plan_versions
        WHERE user_id = :u AND approved = true ORDER BY id DESC LIMIT 1
    """), {"u": user["id"]}).mappings().first()
    if not row:
        raise HTTPException(404, "no plan for this user — run: python -m app.create_user")
    return dict(row)

@router.get("/plan/history")
def plan_history(limit: int = 50, db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    """Your plan's full audit trail, newest first: every version with its
    RFC6902 patch, rationale, source (seed|agent|user), and approval state.
    Append-only storage makes this a plain SELECT."""
    rows = db.execute(text("""
        SELECT id, created_at, source, approved, rationale, patch,
               plan->'targets' AS targets
        FROM plan_versions WHERE user_id = :u
        ORDER BY id DESC LIMIT :n
    """), {"u": user["id"], "n": limit}).mappings().all()
    return [dict(r) for r in rows]

@router.post("/plan/approvals/{approval_id}/{decision}")
def resolve_approval(approval_id: int, decision: str, db: Session = Depends(get_db),
                     user: dict = Depends(get_current_user)):
    """decision: approve | reject. Called by the worker (with the owner's token)
    when a Telegram button is pressed. Ownership is enforced: you can only
    resolve approvals on your own plan."""
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve|reject")
    row = db.execute(text("""
        SELECT a.plan_version_id FROM pending_approvals a
        JOIN plan_versions p ON p.id = a.plan_version_id
        WHERE a.id = :i AND a.status = 'pending' AND p.user_id = :u
    """), {"i": approval_id, "u": user["id"]}).first()
    if not row:
        raise HTTPException(404, "no pending approval with that id for this user")
    if decision == "approve":
        db.execute(text("UPDATE plan_versions SET approved=true WHERE id=:p"), {"p": row[0]})
    db.execute(text(
        "UPDATE pending_approvals SET status=:s, resolved_at=now() WHERE id=:i"
    ), {"s": decision + "d", "i": approval_id})
    db.commit()
    return {"ok": True, "decision": decision}
