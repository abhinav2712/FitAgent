"""The agent loop — a plain, debuggable while-loop over Anthropic tool use.
~80 lines. No framework. Every run is audited into agent_runs.

Every invocation is on behalf of exactly one user: the user dict is resolved
by the caller (worker/CLI) from the users table and injected into every tool
call by Python — the LLM never picks the user.
"""
import json
from datetime import date
from anthropic import Anthropic
from sqlalchemy import text
from app.config import settings
from app.db import SessionLocal
from agent import tools, prompts

# base_url override lets any Anthropic-compatible server stand in for the
# Claude API (Ollama for free local models) — the loop, tools, and guardrails
# are identical either way.
client = Anthropic(api_key=settings.anthropic_api_key,
                   base_url=settings.anthropic_base_url or None)
MAX_TURNS = 8

def run(user: dict, trigger: str, user_message: str) -> tuple[int, str]:
    """Returns (agent_run_id, final_text) — the id lets callers link the run
    to what triggered it (e.g. comments.agent_run_id for the in-app chat)."""
    messages = [{"role": "user", "content": user_message}]
    tool_call_log, tokens_in, tokens_out = [], 0, 0
    final_text = ""

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=settings.agent_model,
            max_tokens=2000,
            system=prompts.system_for(user),
            tools=tools.TOOLS,
            messages=messages,
        )
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
            out = tools.handle(user, tu.name, tu.input)
            tool_call_log.append({"tool": tu.name, "args": tu.input, "result": out[:500]})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
        messages.append({"role": "user", "content": results})

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
    run(user, "nightly", f"{prompts.NIGHTLY}\n\nToday is {date.today().isoformat()}. "
                         f"Start by calling get_day_context.")

def process_comment(user: dict, comment_id: int, comment_date: str, text_: str) -> tuple[int, str]:
    return run(user, "comment",
               f"{prompts.COMMENT}\n\nDate: {comment_date}\nComment: \"{text_}\"\n"
               f"Start by calling get_day_context.")

def swiggy_window(user: dict):
    run(user, "swiggy_window", f"{prompts.SWIGGY}\n\nToday is {date.today().isoformat()}. "
                               f"Start by calling get_day_context.")
