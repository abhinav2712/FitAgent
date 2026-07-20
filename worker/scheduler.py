"""Worker process: 3 cron triggers + comment inbox polling + Telegram button polling.
Cron triggers fan out over all users (one agent run each, isolated failures).
Schedule runs in settings.user_tz for everyone — per-user timezones are a v2 upgrade."""
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
import httpx
from app.config import settings
from app.db import SessionLocal
from agent import loop, notify

# One definition of the user row the agent needs — _all_users and the comment
# join both derive from it, so adding a column is a one-line change.
USER_FIELDS = ("id", "name", "telegram_chat_id", "profile", "tz", "lat", "lng",
               "location_label", "swiggy_token", "swiggy_token_expires_at")

def _all_users():
    db = SessionLocal()
    try:
        return [dict(r) for r in db.execute(text(
            f"SELECT {', '.join(USER_FIELDS)} FROM users")).mappings()]
    finally:
        db.close()

def _fan_out(fn, label):
    for u in _all_users():
        try:
            fn(u)
        except Exception as e:
            print(f"[worker] {label} failed for user {u['id']} ({u['name']}): {e}")

def nightly_all():
    _fan_out(loop.nightly_review, "nightly")

def swiggy_all():
    _fan_out(loop.swiggy_window, "swiggy")

def process_new_comments():
    db = SessionLocal()
    try:
        rows = db.execute(text(f"""
            SELECT c.id AS comment_id, c.date, c.text,
                   {', '.join('u.' + f for f in USER_FIELDS)}
            FROM comments c JOIN users u ON u.id = c.user_id
            WHERE c.processed = false ORDER BY c.id LIMIT 5
        """)).mappings().all()
        for r in rows:
            user = {k: r[k] for k in USER_FIELDS}
            print(f"[worker] processing comment {r['comment_id']} (user {user['name']}): {r['text'][:60]}")
            run_id, _ = loop.process_comment(user, r["comment_id"], str(r["date"]), r["text"])
            db.execute(text(
                "UPDATE comments SET processed=true, agent_run_id=:r WHERE id=:i"),
                {"r": run_id, "i": r["comment_id"]})
            db.commit()
    finally:
        db.close()

def handle_approval(approval_id: int, decision: str, presser_chat_id: str):
    """Telegram button pressed — resolve via our own API with the OWNER's token
    so ownership is enforced in one place. Ignore presses from anyone who isn't
    the plan's owner (all users share the same bot)."""
    db = SessionLocal()
    try:
        owner = db.execute(text("""
            SELECT u.api_token, u.telegram_chat_id FROM pending_approvals a
            JOIN plan_versions p ON p.id = a.plan_version_id
            JOIN users u ON u.id = p.user_id
            WHERE a.id = :i
        """), {"i": approval_id}).first()
    finally:
        db.close()
    if not owner:
        print(f"[worker] approval {approval_id}: no owner found, ignoring")
        return
    token, owner_chat = owner
    if str(owner_chat) != presser_chat_id:
        print(f"[worker] approval {approval_id}: pressed from chat {presser_chat_id}, "
              f"owner is {owner_chat} — ignoring")
        return
    httpx.post(f"http://api:8000/plan/approvals/{approval_id}/{decision}",
               headers={"X-Api-Token": token}, timeout=10)
    notify.send(owner_chat,
                f"{'✅ Applied' if decision == 'approve' else '❌ Rejected'} (approval {approval_id})")

def telegram_thread():
    offset = 0
    while True:
        try:
            offset = notify.poll_callbacks(handle_approval, offset)
        except Exception as e:
            print(f"[telegram] {e}")
            time.sleep(5)

def main():
    sched = BackgroundScheduler(timezone=settings.user_tz)
    sched.add_job(nightly_all, "cron", hour=22, minute=0)
    sched.add_job(swiggy_all, "cron", hour=18, minute=0)
    sched.add_job(process_new_comments, "interval", seconds=30)
    sched.start()
    threading.Thread(target=telegram_thread, daemon=True).start()
    print("[worker] up — nightly 22:00, swiggy 18:00, comments every 30s (all users)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
