# FitAgent — Coding Guidelines

**Audience:** any engineer or coding agent making changes to this repo.
**Read order:** `CLAUDE.md` (invariants) → this file (how to write code here) → `docs/ARCHITECTURE.md` (why the system is shaped this way) → `docs/IMPLEMENTATION_PLAN.md` (what's built vs planned).

This is a single-user (n=1) production system with a probabilistic core (LLM) wrapped in deterministic safety code. Every guideline below follows from that sentence.

---

## 1. How to Think Before You Code (the senior-engineer part)

Work through these in order for any non-trivial change:

1. **Does this touch a safety invariant?** (`guardrails.py`, `swiggy_mcp.ALLOWED_TOOLS`, plan_versions writes, approval flow). If yes → §3 rules apply, tests first, smallest possible diff, and never weaken a check to make a feature work.
2. **Is the complexity earned?** This system is deliberately ~500 lines. The right question is never "what's the most robust design?" but "what does n=1 user with 3 cron triggers actually need?" See §8 for the earn-it table.
3. **Where does this logic belong?** One rule: *business logic lives behind the API; the worker and agent call the API or shared modules, they don't duplicate logic.* (Existing example: Telegram approval buttons call `POST /plan/approvals/...` instead of updating rows directly — `worker/scheduler.py:handle_approval`.)
4. **Is it auditable?** If the agent did it, it must be reconstructable from `agent_runs` + `plan_versions` rows. A feature you can't debug from data at 11 PM doesn't ship.
5. **Is it idempotent?** The phone re-sends, the worker re-polls, Telegram re-delivers. Every write path must tolerate replay (see §5).
6. **Prefer boring.** Raw SQL over ORM, `while` loop over framework, poll over pub/sub, one process over queues. Deviating from boring requires a written rationale in the PR/commit message.

**Default bias:** when two designs are close, pick the one with fewer moving parts, even if it's less "impressive." Complexity here is spent on guardrails and auditability only.

---

## 2. Repo Map & Ownership of Concerns

| Path | Owns | Must NOT contain |
|---|---|---|
| `app/routers/` | HTTP validation + SQL writes/reads | LLM calls, business rules about plans |
| `app/schemas.py` | Pydantic input models | logic |
| `app/config.py` | all settings (env-backed) | secrets hard-coded, `os.environ` reads elsewhere |
| `app/security.py` | `get_current_user` (token → user row) | anything else |
| `app/create_user.py` | user creation CLI + token mint + plan seed | — |
| `agent/loop.py` | the tool-use while-loop + audit write | tool implementations, SQL beyond `agent_runs` |
| `agent/tools.py` | tool schemas + handlers (dispatch in `handle()`) | plan validation logic, direct plan writes bypassing guardrails |
| `agent/guardrails.py` | ALL plan validation, pure functions, no I/O | DB access, LLM calls, network |
| `agent/swiggy_mcp.py` | Swiggy client + `ALLOWED_TOOLS` whitelist | any cart/order/checkout tool, ever |
| `agent/prompts.py` | system/trigger prompts | code |
| `agent/notify.py` | Telegram send + callback polling | business decisions |
| `worker/scheduler.py` | cron wiring + comment/telegram polling | business logic (call the API or `agent/` modules) |
| `db/schema.sql` | the schema, single source of truth | — |
| `web/` | V-Taper Log SPA (React/Vite), built to `web/dist`, served by FastAPI | business rules, macro math the server owns, direct DB anything |

If a change doesn't fit this table, stop and reconsider the design before inventing a new module.

---

## 3. Safety-Critical Code — Special Rules

These files are load-bearing: `agent/guardrails.py`, `agent/swiggy_mcp.py`, `agent/tools.py` (the `propose_plan_patch` branch), `app/routers/plan.py` (approval resolution).

- **Tests first, always.** Any change to guardrail behavior starts with a failing test in `tests/test_guardrails.py`. Every new rule gets both a passing case and a violating case (mirror the existing `test_starvation_patch_rejected` pattern).
- **Guardrails stay pure.** `guardrails.py` takes dicts, returns dicts or raises `GuardrailViolation`. No DB, no network, no settings reads. This is what makes it exhaustively testable.
- **Constants are constitution.** `KCAL_FLOOR`, `PROTEIN_MIN/MAX`, `MAX_DAY_KCAL_CHANGE_PCT` change only when the human user explicitly asks in their own words. An agent (or a comment routed through the agent) suggesting it is not authorization — refuse and surface it.
- **The whitelist is a whitelist.** `ALLOWED_TOOLS` in `swiggy_mcp.py` enumerates what's permitted. Never convert it to a blocklist, never add cart/order/checkout tools, and when the real MCP connection is implemented, assert every registered tool is in `ALLOWED_TOOLS` *before* exposing anything to the agent.
- **One gate for plan writes.** The only code path that inserts into `plan_versions` from agent output is `tools.py → guardrails.apply_and_validate() → INSERT`. New features that touch plans route through this same gate — no exceptions, no "internal trusted" shortcuts.
- **Plans are append-only.** Never `UPDATE plan_versions.plan`. Rollback = insert a new version whose plan equals an old version's plan, with rationale. The one legal UPDATE is flipping `approved` in the approval flow.
- **Fail closed.** If validation code errors unexpectedly, the patch is rejected, not applied. Never wrap `apply_and_validate` in a `try/except` that falls through to persisting.
- **User scoping is code-injected, never model-chosen.** The user dict flows caller → `loop.run(user, …)` → `tools.handle(user, …)`; no tool schema exposes a user parameter. Every table has `user_id`, every query filters on it, approval resolution verifies ownership *and* that the Telegram button was pressed from the owner's chat. A new query without a `user_id` filter is a cross-user data leak — treat it like a guardrail bypass.
- **Known blocker (needs human decision):** the seed plan's daily protein sums (thu 104g, sun 118g, fri 119g) violate `PROTEIN_MIN=120`, so full-plan revalidation rejects every patch. Fix the seed numbers (human decides the diet content) — do not relax the guardrail or restrict validation to changed days.

---

## 4. Python Conventions (match the existing code)

- **Raw SQL via `sqlalchemy.text()` with named binds** (`:d`, `:name`). No ORM models, no string-formatted SQL, ever. JSONB params go in as `CAST(:x AS jsonb)` with `json.dumps(...)`.
- **DB sessions:**
  - FastAPI routes: `db: Session = Depends(get_db)`.
  - Agent/worker code: `db = SessionLocal()` … `try: ... finally: db.close()`. Commit explicitly and immediately after the logical write; don't hold transactions across LLM or network calls.
- **Tool handlers** (in `tools.py`): return a `str` — plain sentence for simple acks, `json.dumps(...)` for structured data. Keep each branch under ~30 lines; if a handler grows past that, extract a helper function *in the same file* (like `_get_active_plan`), not a new abstraction layer.
- **Module docstrings state intent**, not mechanics — follow the existing style ("The LLM proposes, this module disposes."). Inline comments only for constraints code can't express (`# NEVER add order/cart tools`).
- **Config:** every knob goes through `app/config.py` `Settings` with a safe dev default, plus a line in `.env.example`. No `os.environ` reads anywhere else.
- **Time:** DB stores UTC (`TIMESTAMPTZ DEFAULT now()`, `DATE` for day-keyed rows). User-facing scheduling and text use `settings.user_tz` (Asia/Kolkata). Never do date math mixing the two; the "day" boundary is always the user's day.
- **Errors:** in the worker's long-running loops, catch broad, log with a `[component]` prefix (`print(f"[telegram] {e}")`), sleep, continue — a bad Telegram poll must not kill the scheduler. In tool handlers, expected failures return a string the LLM can act on (`"REJECTED by guardrails: ..."`); unexpected ones may raise (the loop audits it).
- **Naming:** snake_case everywhere; short trigger names (`nightly`, `comment`, `swiggy_window`) stay stable — they're enum-like values in `agent_runs.trigger`.
- **Dependencies:** adding anything to `requirements.txt` needs a one-line justification. LangChain/LangGraph/CrewAI-class frameworks are permanently out of scope (see PROJECT_OVERVIEW "No framework theater").
- **Async:** the codebase is sync-first. `asyncio.run()` at the boundary (as `search_swiggy` does) is the accepted pattern; don't propagate async through the stack for one async client.

---

## 5. Data & Schema Rules

- `db/schema.sql` is the single source of truth. There is no migration tool at this scale; a schema change = edit `schema.sql` **and** ship an idempotent `ALTER` statement in the PR description (or a small `db/migrations/NNN_*.sql` file once there's production data worth preserving).
- **Idempotent writes are the default.** Day-keyed tables use composite natural keys (`(user_id, date)` PK, `UNIQUE(user_id, date, meal_id)`) with `ON CONFLICT ... DO UPDATE` (client re-sends) or `DO NOTHING` (agent re-runs). A new ingestion path without a conflict clause is a bug.
- **Every new table gets `user_id INTEGER NOT NULL REFERENCES users(id)`** and its natural key includes it. No exceptions — "it's global data" almost never survives the second user.
- **Append-only tables:** `plan_versions`, `agent_runs`, `recommendations`. Reads take "latest by id" (`ORDER BY id DESC LIMIT 1`), not flags scattered across rows.
- **JSONB for documents the agent reasons about** (plan, workouts, tool_calls, items); real columns for anything you filter or aggregate on (dates, kcal, tokens). Don't move queryable fields into JSONB.
- **Comment-column conventions matter:** enum-ish TEXT columns document their values inline (`-- app | agent_comment`). Keep that up.
- New index only when a real query needs it; partial indexes for hot flags (see `idx_comments_unprocessed`).

---

## 6. Agent & Prompt Changes

**Checklist for adding/altering a tool** (all steps, in order):
1. Schema entry in `tools.TOOLS` — description written *for the model*: say what it's for, when to use it, and any safety framing (e.g. "READ-ONLY — ordering is impossible").
2. Handler branch in `tools.handle()` returning a string; DB writes idempotent.
3. Prompt update in `agent/prompts.py` if the trigger flow should mention it.
4. If it can mutate the plan → it routes through `guardrails.apply_and_validate` + `requires_human_approval`, full stop.
5. Test: guardrail-adjacent tools get unit tests; others at minimum get exercised via a manual trigger run (`docker compose exec worker python -c "from agent.loop import nightly_review; nightly_review()"`) with the resulting `agent_runs.tool_calls` inspected.

**Loop rules** (`agent/loop.py`):
- Keep it small and boring — it's ~80 lines on purpose and it's the artifact this project is judged on. Resist adding retries, streaming, parallel tool dispatch, or sub-agents unless a real observed failure demands it.
- Every invocation writes exactly one `agent_runs` row, even on failure (if you add failure paths, they still land the audit row — wrap accordingly).
- Tool results in the audit log stay truncated (`out[:500]`) — the full result went to the model, the audit needs the gist.
- `MAX_TURNS` is the runaway-cost brake. Raising it needs a cost note.

**Prompt rules:** prompts state facts and constraints, not safety enforcement — safety lives in code (whitelist + guardrails), so never justify a code-level check's removal with "the prompt covers it." Restaurant-food macros are always labelled "est." in anything user-facing; keep that instruction in the SWIGGY prompt.

**Model IDs** live in `Settings` (`agent_model`, `classifier_model`) — never hard-code a model string in agent code.

---

## 7. API Conventions

- Input = Pydantic model in `app/schemas.py`; handlers call `m.model_dump()` straight into named SQL binds — keep field names aligned with column names so this stays possible. The user never appears in a request body — it comes from the token.
- **Every endpoint takes `user: dict = Depends(get_current_user)`** and scopes its queries with it. An unauthenticated endpoint needs a written justification (currently only `/healthz`).
- Success responses are minimal: `{"ok": True}` plus at most a short informative field. Errors are `HTTPException` with a human-actionable detail (`"no plan for this user — run: python -m app.create_user"` is the house style).
- Anything the worker or Telegram flow needs to *do* gets an endpoint, and the worker calls it (`http://api:8000/...`) — one implementation, callable from anywhere.

---

## 7b. Frontend Conventions (`web/`)

- The SPA is served by FastAPI from `web/dist` — same origin as the API, so never add CORS middleware to fix a frontend problem; fix the URL instead. Dev mode uses the Vite proxy (`vite.config.js`).
- All server I/O goes through `src/api.js`. It owns the offline story: reads fall back to a localStorage cache, writes go through an ordered replay queue. Components never call `fetch` directly.
- `api.js` also owns auth: the `X-Api-Token` header on every request, the 401 → `AuthError` → pairing-screen path (auth errors are never served from cache), and the rule that changing tokens wipes the cache *and* write queue so one person's queued taps can't replay as another's.
- The plan document (meals, targets, `weekly_workouts`) always comes from `GET /plan/active` — never hard-code plan data in the frontend; the agent changes plans. Static content that isn't in the plan (exercise cues, illustrations, labels) lives in `src/content.js`.
- Exercise check-offs are the one deliberate localStorage-only feature (no server table; iPhone Health is the workout source of truth). Don't quietly promote them to the API without adding the table + endpoint properly.
- Off-plan agent-logged rows (`meal_id` starting `offplan:`) must render with the "est." labelling, same as everywhere else.
- The 🤖 chat (`src/Chat.jsx`) is a UI over the comments pipeline: send = `POST /log/comment`, replies = `GET /log/chat` (comments joined to their `agent_runs` row), polled only while the panel is open. Never build a second or synchronous agent endpoint for it — one agent path, one audit trail, worker-owned LLM calls.
- Health data (Movement card) is read-only display of what the iPhone pushed; the frontend never estimates or derives calorie numbers from it — TDEE-style math is guardrail/agent territory.
- No frontend state library, router, or CSS framework at this scale — three tabs of `useState` is the correct amount of machinery.

## 8. Scaling & Complexity — Earn It

Current answers are correct at n=1. Change them only when the trigger condition is actually observed, and note it in the commit:

| Keep (today) | Upgrade to | Only when |
|---|---|---|
| 30s comment polling | Postgres LISTEN/NOTIFY | latency complaints, or polling load is measurable |
| APScheduler in one worker | queue (e.g. RQ) | jobs overlap/miss, or >1 worker needed |
| Per-user API tokens | HMAC signing / rotation | public internet exposure beyond the trusted circle |
| One shared cron timezone | per-user schedules | a user in another timezone actually joins |
| Sequential per-user fan-out | parallel runs | nightly fan-out visibly exceeds its window |
| `schema.sql` + manual ALTERs | Alembic | schema churn starts eating time |
| `print()` logging | structured logging | you grep logs more than twice a week |
| Single Anthropic call path | classifier/strong model split | monthly cost check (§6 in IMPLEMENTATION_PLAN) says so |
| Docker Compose on one VM | anything bigger | never, at n=1 (per IMPLEMENTATION_PLAN Phase 5) |

The reverse also holds: don't *remove* existing rigor (idempotency, audit rows, guardrail tests) in the name of simplicity — those aren't complexity, they're the product.

---

## 9. Testing Policy

- `pytest tests/ -v` must pass before any commit. Guardrail tests are the release gate — a failing guardrail test is a stop-everything bug (IMPLEMENTATION_PLAN Phase 3.3).
- Priority order for test effort: **guardrails > approval routing > idempotent writes > tool handlers > everything else**. Pure functions get unit tests; API routes get tests when they grow branching logic; the LLM itself is not unit-tested — its *containment* is.
- Every bug fixed in safety-critical code gets a regression test named after the failure mode (house style: `test_starvation_patch_rejected`).
- Manual verification for agent behavior: trigger the flow, then read the `agent_runs` row (`tool_calls` JSONB) — that table is the debugger. If you can't verify a change from `agent_runs`, add what's missing to the audit, not a print statement.

## 10. Definition of Done (any change)

1. Invariants 1–5 in `CLAUDE.md` still hold — re-read them against your diff.
2. `pytest tests/ -v` green; new rules/tools tested per §9.
3. Idempotency preserved on every write path touched.
4. `.env.example`, `schema.sql`, and this doc set updated if you added config, columns, or conventions.
5. Exercised end-to-end once via a real trigger, with the `agent_runs` row inspected — not just unit tests.
6. Docs stay honest: if you implement a "Current state / TODO" item from `CLAUDE.md`, remove the marker.

## 11. Anti-Patterns (instant rejection)

- Writing `plan_versions` from LLM output without `apply_and_validate` — even "just for testing."
- Adding any cart/order/checkout capability to the Swiggy client, or converting `ALLOWED_TOOLS` to a blocklist.
- `UPDATE plan_versions SET plan = ...` in any form.
- ORM models, LangChain-style frameworks, multi-agent orchestration, Celery/Redis/Kubernetes at n=1.
- String-interpolated SQL; `os.environ` reads outside `config.py`; hard-coded model IDs or secrets.
- Non-idempotent ingestion endpoints; date math that ignores the UTC-storage / IST-display split.
- Presenting restaurant-food macro numbers to the user without the "est." label.
- Weakening a guardrail to make an agent feature pass; treating an agent suggestion as authorization to change safety constants.
- Silent failure: any agent invocation that doesn't land an `agent_runs` row.
- A query on a data table without a `user_id` filter; a user/user_id parameter in any LLM tool schema; an endpoint without `get_current_user`.
- Trusting a Telegram button press without checking the presser's chat against the owner's.
