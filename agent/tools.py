"""Tool definitions + handlers for the agent loop.
Every handler is small, synchronous-ish, and audited by the loop.

SCOPING: handle() receives the user dict from the loop and injects user_id
into every query. The user is never a tool parameter — the LLM cannot read
or write another user's data by construction.
"""
import json
import asyncio
from datetime import date as Date
from sqlalchemy import text
from app.db import SessionLocal
from agent import guardrails, swiggy_mcp, notify

TOOLS = [
    {"name": "get_day_context",
     "description": "Get today's full context: active plan for the weekday, logged meals, health metrics, weight, unprocessed comments.",
     "input_schema": {"type": "object", "properties": {
         "date": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["date"]}},
    {"name": "log_offplan_food",
     "description": "Log food the user ate that wasn't in the plan (from a comment). Use realistic Indian-food calorie estimates.",
     "input_schema": {"type": "object", "properties": {
         "date": {"type": "string"}, "name": {"type": "string"},
         "est_kcal": {"type": "integer"}, "est_protein_g": {"type": "integer"}},
         "required": ["date", "name", "est_kcal", "est_protein_g"]}},
    {"name": "propose_plan_patch",
     "description": "Propose a change to the plan as an RFC6902 JSON Patch array against the plan document, with a one-line rationale. Valid paths look like /meals/<mon..sun>/items/<index>/kcal, /meals/wed/items/2/name, or /targets/kcal — NOT the get_day_context keys (plan_today etc.). May be rejected by validation.",
     "input_schema": {"type": "object", "properties": {
         "patch": {"type": "array", "items": {"type": "object"}},
         "rationale": {"type": "string"}}, "required": ["patch", "rationale"]}},
    {"name": "search_swiggy",
     "description": "Search nearby Swiggy dishes (READ-ONLY — ordering is impossible). Returns dishes with price and description; you estimate macros.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}}, "required": ["query"]}},
    {"name": "create_recommendation",
     "description": "Persist tonight's order recommendations (max 3 items).",
     "input_schema": {"type": "object", "properties": {
         "date": {"type": "string"},
         "items": {"type": "array", "items": {"type": "object"}},
         "remaining_kcal": {"type": "integer"},
         "remaining_protein": {"type": "integer"}},
         "required": ["date", "items", "remaining_kcal", "remaining_protein"]}},
    {"name": "notify_user",
     "description": "Send the user a Telegram message. Use Markdown, keep it short.",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string"}}, "required": ["text"]}},
    {"name": "add_day_note",
     "description": "Record a one-line day adjustment shown on the user's Today screen. Use for non-food deviations: workout skipped or substituted, injury accommodation, schedule note (e.g. 'Rest-day walk skipped — 20 min yoga instead'). Not for food (use log_offplan_food) and not a plan change.",
     "input_schema": {"type": "object", "properties": {
         "date": {"type": "string"}, "note": {"type": "string"}},
         "required": ["date", "note"]}},
]

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def _get_active_plan(db, user_id: int):
    row = db.execute(text("""
        SELECT id, plan FROM plan_versions
        WHERE user_id=:u AND approved=true ORDER BY id DESC LIMIT 1
    """), {"u": user_id}).first()
    return (row[0], row[1]) if row else (None, None)

def handle(user: dict, name: str, args: dict) -> str:
    uid = user["id"]
    db = SessionLocal()
    try:
        if name == "get_day_context":
            d = Date.fromisoformat(args["date"])
            plan_id, plan = _get_active_plan(db, uid)
            wd = WEEKDAYS[d.weekday()]
            meals = [dict(r) for r in db.execute(text(
                "SELECT meal_id, name, kcal, protein_g, checked FROM meal_logs WHERE user_id=:u AND date=:d"),
                {"u": uid, "d": d}).mappings()]
            health = db.execute(text(
                "SELECT steps, active_kcal, workouts FROM health_metrics WHERE user_id=:u AND date=:d"),
                {"u": uid, "d": d}).mappings().first()
            weight = db.execute(text(
                "SELECT weight_kg FROM weight_logs WHERE user_id=:u AND date=:d"),
                {"u": uid, "d": d}).first()
            return json.dumps({
                "weekday": wd,
                "plan_targets": plan["targets"] if plan else None,
                "plan_today": plan["meals"].get(wd) if plan else None,
                "workout_today": plan["weekly_workouts"].get(wd) if plan else None,
                "logged_meals": meals,
                "health": dict(health) if health else None,
                "weight_kg": float(weight[0]) if weight else None,
            }, default=str)

        if name == "log_offplan_food":
            db.execute(text("""
                INSERT INTO meal_logs (user_id, date, meal_id, name, kcal, protein_g, checked, source)
                VALUES (:u, :d, 'offplan:' || :name, :name, :k, :p, true, 'agent_comment')
                ON CONFLICT (user_id, date, meal_id) DO NOTHING
            """), {"u": uid, "d": args["date"], "name": args["name"][:40],
                   "k": args["est_kcal"], "p": args["est_protein_g"]})
            db.commit()
            return f"logged: {args['name']} ~{args['est_kcal']} kcal"

        if name == "propose_plan_patch":
            plan_id, plan = _get_active_plan(db, uid)
            try:
                new_plan = guardrails.apply_and_validate(plan, args["patch"])
            except guardrails.GuardrailViolation as e:
                return f"REJECTED by guardrails: {e}. Propose a smaller change."
            needs_human = guardrails.requires_human_approval(args["patch"])
            row = db.execute(text("""
                INSERT INTO plan_versions (user_id, plan, patch, rationale, source, approved)
                VALUES (:u, CAST(:pl AS jsonb), CAST(:pa AS jsonb), :r, 'agent', :ap)
                RETURNING id
            """), {"u": uid, "pl": json.dumps(new_plan), "pa": json.dumps(args["patch"]),
                   "r": args["rationale"], "ap": not needs_human}).first()
            db.commit()
            if needs_human:
                a = db.execute(text("""
                    INSERT INTO pending_approvals (plan_version_id, summary)
                    VALUES (:p, :s) RETURNING id
                """), {"p": row[0], "s": args["rationale"]}).first()
                db.commit()
                notify.send(user["telegram_chat_id"],
                            f"🤖 Plan change proposed:\n_{args['rationale']}_", approval_id=a[0])
                return f"queued for user approval (approval id {a[0]})"
            return f"applied as plan version {row[0]}"

        if name == "search_swiggy":
            return json.dumps(asyncio.run(swiggy_mcp.search_dishes(args["query"])))

        if name == "create_recommendation":
            db.execute(text("""
                INSERT INTO recommendations (user_id, date, items, remaining_kcal, remaining_protein)
                VALUES (:u, :d, CAST(:i AS jsonb), :k, :p)
            """), {"u": uid, "d": args["date"], "i": json.dumps(args["items"][:3]),
                   "k": args["remaining_kcal"], "p": args["remaining_protein"]})
            db.commit()
            return "recommendation saved"

        if name == "notify_user":
            notify.send(user["telegram_chat_id"], args["text"])
            return "sent"

        if name == "add_day_note":
            db.execute(text("""
                INSERT INTO day_notes (user_id, date, note) VALUES (:u, :d, :n)
                ON CONFLICT (user_id, date, note) DO NOTHING
            """), {"u": uid, "d": args["date"], "n": args["note"][:200]})
            db.commit()
            return f"noted on Today screen: {args['note'][:80]}"

        return f"unknown tool {name}"
    finally:
        db.close()
