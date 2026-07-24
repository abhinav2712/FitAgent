"""Live chat delivery — Postgres LISTEN/NOTIFY, not a new agent path.

The worker is still the only thing that ever invokes the agent (comment poll,
same as before). This module just lets that already-running invocation publish
its own progress so an open chat panel can render it live instead of waiting
for the next poll tick. Best-effort only: if no one is listening when an event
fires, it's simply not seen — GET /log/chat (backed by agent_runs) remains the
durable record, same as Con-Mon separates its SSE stream from durable chat
history. Never invoke the agent from here.
"""
import json
from sqlalchemy import text
from app.db import SessionLocal

# Tool name -> short user-facing label for the "activity" event. Anything not
# listed here still streams (falls back to the raw name) rather than vanishing.
ACTIVITY_LABELS = {
    "get_day_context": "Checking your day",
    "log_offplan_food": "Logging that",
    "propose_plan_patch": "Considering a plan change",
    "search_swiggy": "Searching nearby restaurants",
    "search_instamart": "Searching Instamart",
    "create_recommendation": "Saving picks",
    "add_day_note": "Making a note",
    "notify_user": "Sending you a message",
}

def publish(user_id: int, event: dict):
    """Fire-and-forget: NOTIFY takes effect at commit, so each event gets its
    own short-lived commit — that's what makes delivery live rather than
    batched until the run finishes."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT pg_notify(:ch, :payload)"),
                  {"ch": f"agent_chat_{user_id}", "payload": json.dumps(event)})
        db.commit()
    except Exception as e:  # a dropped NOTIFY must never break the agent run
        print(f"[chat_stream] publish failed for user {user_id}: {e}")
    finally:
        db.close()
