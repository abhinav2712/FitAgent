"""The agent loop — a plain, debuggable while-loop over Anthropic tool use.
~80 lines. No framework. Every run is audited into agent_runs.

Every invocation is on behalf of exactly one user: the user dict is resolved
by the caller (worker/CLI) from the users table and injected into every tool
call by Python — the LLM never picks the user.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from anthropic import Anthropic
from sqlalchemy import text
from app.config import settings
from app.db import SessionLocal
from agent import tools, prompts, chat_stream

# base_url override lets any Anthropic-compatible server stand in for the
# Claude API (Ollama for free local models) — the loop, tools, and guardrails
# are identical either way.
client = Anthropic(api_key=settings.anthropic_api_key,
                   base_url=settings.anthropic_base_url or None)
MAX_TURNS = 8

ACTION_TOOLS = ("log_offplan_food", "propose_plan_patch", "create_recommendation")

def _today() -> str:
    """The user's day, not the container's: the worker runs in UTC, so a
    date.today() after 00:00 IST would stamp cron runs with yesterday."""
    return datetime.now(ZoneInfo(settings.user_tz)).date().isoformat()

def _fallback_reply(tool_call_log: list) -> str:
    """Small/local models sometimes end a run on a bare tool call with no text.
    The chat still deserves a reply: prefer what the agent sent via notify_user
    (the user-facing message by design); else summarize the actions actually
    taken (tool results are human-readable); else empty → UI fallback bubble."""
    notes = [c["args"].get("text") for c in tool_call_log if c["tool"] == "notify_user"]
    if any(notes):
        return notes[-1]
    acted = [c["result"] for c in tool_call_log if c["tool"] in ACTION_TOOLS]
    return "✓ " + "; ".join(acted) if acted else ""

def run(user: dict, trigger: str, user_message: str, on_event=None) -> tuple[int, str]:
    """Returns (agent_run_id, final_text) — the id lets callers link the run
    to what triggered it (e.g. comments.agent_run_id for the in-app chat).

    on_event(dict), if given, is called live as the run progresses — "delta"
    per streamed text chunk, "activity" before each tool call, "done" once —
    so an open chat panel can render it (see agent/chat_stream.py). Purely a
    UX side channel: nothing here changes what gets persisted or how."""
    messages = [{"role": "user", "content": user_message}]
    tool_call_log, tokens_in, tokens_out = [], 0, 0
    final_text = ""

    for _ in range(MAX_TURNS):
        with client.messages.stream(
            model=settings.agent_model,
            max_tokens=2000,
            system=prompts.system_for(user),
            tools=tools.TOOLS,
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                if on_event:
                    on_event({"type": "delta", "text": chunk})
            resp = stream.get_final_message()
        tokens_in += resp.usage.input_tokens
        tokens_out += resp.usage.output_tokens

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        texts = [b.text for b in resp.content if b.type == "text"]
        if texts:
            final_text = "\n".join(texts)

        if not tool_uses:
            break

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            if on_event:
                on_event({"type": "activity", "tool": tu.name})
            out = tools.handle(user, tu.name, tu.input)
            tool_call_log.append({"tool": tu.name, "args": tu.input, "result": out[:500]})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
        messages.append({"role": "user", "content": results})

    if not final_text:
        final_text = _fallback_reply(tool_call_log)
    if on_event:
        on_event({"type": "done", "text": final_text})

    db = SessionLocal()
    try:
        row = db.execute(text("""
            INSERT INTO agent_runs (user_id, trigger, input_context, tool_calls, output_text, tokens_in, tokens_out)
            VALUES (:u, :t, CAST(:i AS jsonb), CAST(:c AS jsonb), :o, :ti, :to)
            RETURNING id
        """), {"u": user["id"], "t": trigger,
               "i": json.dumps({"message": user_message}),
               "c": json.dumps(tool_call_log), "o": final_text,
               "ti": tokens_in, "to": tokens_out}).first()
        db.commit()
    finally:
        db.close()
    return row[0], final_text

def nightly_review(user: dict):
    run(user, "nightly", f"{prompts.NIGHTLY}\n\nToday is {_today()}. "
                         f"Start by calling get_day_context.")

def process_comment(user: dict, comment_id: int, comment_date: str, text_: str) -> tuple[int, str]:
    def emit(event):
        if event["type"] == "activity":
            event = {**event, "label": chat_stream.ACTIVITY_LABELS.get(event["tool"], event["tool"])}
        chat_stream.publish(user["id"], {**event, "comment_id": comment_id})
    return run(user, "comment",
               f"{prompts.COMMENT}\n\nDate: {comment_date}\nComment: \"{text_}\"\n"
               f"Start by calling get_day_context.", on_event=emit)

def swiggy_window(user: dict):
    run(user, "swiggy_window", f"{prompts.SWIGGY}\n\nToday is {_today()}. "
                               f"Start by calling get_day_context.")
