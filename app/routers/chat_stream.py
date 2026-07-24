"""Live chat delivery over SSE. Deliberately NOT the usual Depends(get_db)
pattern: LISTEN/NOTIFY needs one dedicated, long-lived connection per open
stream, not a short request-scoped session — so this talks to psycopg2
directly. This endpoint only relays events the worker already published via
agent/chat_stream.py; it never invokes the agent (see CLAUDE.md: "never add
a second/synchronous agent endpoint for chat" — this isn't one, it's a
read-only tap on the worker's existing run).
"""
import select
import psycopg2
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.config import settings
from app.security import get_current_user

router = APIRouter()

def _events(user_id: int):
    """Plain (non-async) generator — Starlette runs it in a thread pool via
    iterate_in_threadpool, so the blocking select()/poll() below never stalls
    the API's event loop. One thread per open chat panel; trivial at this
    user count."""
    dsn = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
    conn = psycopg2.connect(dsn)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"LISTEN agent_chat_{user_id};")
    try:
        yield ": connected\n\n"
        while True:
            if not select.select([conn], [], [], 25)[0]:
                yield ": keep-alive\n\n"  # SSE comment — holds the connection through idle gaps
                continue
            conn.poll()
            while conn.notifies:
                yield f"data: {conn.notifies.pop(0).payload}\n\n"
    finally:
        cur.close()
        conn.close()

@router.get("/log/chat/stream")
def chat_stream_endpoint(user: dict = Depends(get_current_user)):
    return StreamingResponse(_events(user["id"]), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
