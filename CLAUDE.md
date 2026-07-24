# CLAUDE.md — FitAgent

Personal agentic fitness/diet system for a handful of users (Abhi + people he sets it
up for) on one deploy. FastAPI + Postgres + a hand-rolled Anthropic tool-use loop.
No LangChain. No multi-agent. Keep it that way.

## Commands
```bash
docker compose up --build          # full stack (db + api :8000 + worker); tracker UI at :8000/
docker compose exec api python -m app.create_user "Abhi" --chat-id 123   # per person; prints API token
pytest tests/ -v                   # run tests (guardrails are the critical ones)
docker compose logs -f worker      # watch the agent think
cd web && npm run dev              # tracker UI dev server :5173, proxies API to :8000
```
Local dev without Docker: postgres on :5432, `uvicorn app.main:app --reload`,
`python -m worker.scheduler` in a second terminal.

## Architecture (1-minute version)
iPhone Shortcut → POST /webhook/health → Postgres ← POST /log/* ← tracker web app
(`web/` — React/Vite SPA, built to web/dist and served by FastAPI at `/`, same origin, no CORS).
Multi-user: every request carries a per-user X-Api-Token (users table; minted by
`app.create_user`); every table row has user_id; cron triggers fan out over all users.
Worker triggers agent (nightly 22:00, swiggy 18:00, comment poll 5s).
Agent = `agent/loop.py` while-loop over tools in `agent/tools.py`.
The tracker's 🤖 chat IS the comments pipeline: messages → POST /log/comment, worker
links each comment to its agent_runs row, replies surface via GET /log/chat (+ Telegram).
While the worker's run is in flight it also publishes live activity/text-delta events
over Postgres NOTIFY (`agent/chat_stream.py`), relayed to the browser over SSE
(`GET /log/chat/stream`) — a watch-only tap, not a second invocation path.
Never add a second/synchronous agent endpoint for chat.
Plan changes = RFC6902 patches → `agent/guardrails.py` validation → auto-apply or
Telegram approval. Swiggy via `agent/swiggy_mcp.py` (mock until Builders Club approval).
Full details: docs/ARCHITECTURE.md. Coding standards & decision rules: docs/CODING_GUIDELINES.md.
User-facing behavior contract: docs/CAPABILITIES.md — update it in the same commit as any behavior change.

## Invariants — do not break these, ever
1. **The LLM proposes, Python disposes.** All plan mutations go through
   `guardrails.apply_and_validate()`. Never add a code path that writes
   plan_versions from LLM output without it.
2. **Swiggy is read-only by construction.** `ALLOWED_TOOLS` in swiggy_mcp.py must
   never contain cart/order/checkout tools. This is a whitelist, not a blocklist.
3. **Plans are append-only.** Never UPDATE plan_versions.plan. New version + patch + rationale.
4. **kcal floor 1600, protein 120–150g** — hard-coded in guardrails.py. Changing these
   constants requires the human user asking explicitly, not an agent suggestion.
5. Structural changes (targets, weekly_workouts, >4 patch ops) require human approval
   via pending_approvals — resolved from the tracker's approval card or Telegram
   buttons, both through POST /plan/approvals/{id}/{decision} (ownership-checked).
6. **User scoping is injected by Python, never chosen by the LLM.** The user is not a
   tool parameter; `tools.handle(user, ...)` binds user_id into every query. Every new
   table gets a user_id column; every new query filters on it; approval resolution
   verifies ownership (and the Telegram presser's chat id).

## Conventions
- Raw SQL via sqlalchemy `text()` — no ORM models, keep it explicit.
- All timestamps UTC in DB; user-facing times in Asia/Kolkata (worker scheduler tz).
- Tool handlers in agent/tools.py return strings (JSON when structured) and stay <30 lines.
- Every agent invocation must land one row in agent_runs — that table is the debugger.
- Macro numbers for restaurant food are always labelled "est." in user-facing text.

## Current state / TODO markers
- LLM backend is switchable via ANTHROPIC_BASE_URL (empty = Claude API; an
  Anthropic-compatible server like Ollama = free local dev). Same loop, tools,
  and guardrails either way — never fork the agent code per backend.
- swiggy_mcp.py: real MCP client implemented (streamable HTTP, per-user OAuth token
  from `python -m app.swiggy_auth <user_id>` — phone+OTP, 5-day expiry, no refresh).
  SWIGGY_MOCK=true until a user links; whitelist tests in tests/test_swiggy_whitelist.py.
- security.py: per-user X-Api-Token header; HMAC signing is still the v2 upgrade.
- Worker cron runs in one shared timezone (settings.user_tz); per-user schedules are v2.
- Tracker (web/) talks to the API; localStorage holds the token (pairing screen), the
  offline write queue, and exercise check-offs (no server table — iPhone Health is the
  workout truth).
- personal_tracker.html at repo root is the superseded standalone version; delete once
  the served app is verified on the phone.
