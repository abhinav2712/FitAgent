import httpx
from app.config import settings

API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

def send(chat_id: str | None, text: str, approval_id: int | None = None):
    """Send a Telegram DM to one user's chat; if approval_id given, attach
    Approve/Reject buttons. One bot serves all users — chat_id picks the person."""
    if not settings.telegram_bot_token or not chat_id:
        print(f"[notify:noop chat={chat_id}] {text[:120]}")
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if approval_id is not None:
        payload["reply_markup"] = {"inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{approval_id}"},
            {"text": "❌ Reject",  "callback_data": f"reject:{approval_id}"},
        ]]}
    httpx.post(f"{API}/sendMessage", json=payload, timeout=10)

def poll_callbacks(handle, offset: int) -> int:
    """Long-poll Telegram for button presses; call handle(approval_id, decision,
    presser_chat_id). The presser's chat id lets the worker verify the button
    was tapped by the plan's owner, not another user of the same bot."""
    r = httpx.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
    for u in r.json().get("result", []):
        offset = u["update_id"] + 1
        cb = u.get("callback_query")
        if cb and ":" in cb.get("data", ""):
            decision, approval_id = cb["data"].split(":")
            handle(int(approval_id), decision, str(cb["from"]["id"]))
            httpx.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
    return offset
