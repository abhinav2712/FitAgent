# FitAgent — Technical Architecture
### An agentic workflow that watches your training, understands your comments, adapts your plan, and recommends Swiggy orders that fit your macros

---

## 0. The One Hard Constraint First: Apple Health Has No Cloud API

This is the thing that shapes the whole design. Apple HealthKit data (steps, workout pace, distance, GPS routes) lives **on your iPhone only** — there is no server-side API you can poll. The data must be *pushed out* from the phone itself. Three options, in order of pragmatism:

| Option | Effort | Verdict |
|--------|--------|---------|
| **A. Apple Shortcuts automation** | ~30 min | ✅ **Start here.** A Shortcut runs on a schedule (e.g., 9:30 PM daily), reads Health data (steps, workouts, distance, active energy), and POSTs JSON to your FastAPI webhook via "Get Contents of URL". Free, native, zero code on the phone. Limitation: Shortcuts' Health access is decent for steps/workouts but can't export full GPS route files. |
| **B. Health Auto Export app (~₹500 one-time)** | ~15 min | Upgrade path. Purpose-built iOS app that pushes HealthKit data (including detailed workout metrics) to any REST endpoint on a schedule. More reliable than Shortcuts, richer payloads. |
| **C. Build a tiny SwiftUI app with HealthKit** | Days–weeks | Overkill for v1. Only worth it if this becomes a real product. |

**Design consequence:** the system is *event-driven from the phone*, not polling-based. Your backend receives health data; it never fetches it.

---

## 1. System Overview

```
┌─────────────────────────  DATA SOURCES  ─────────────────────────┐
│                                                                   │
│  iPhone Fitness/Health          V-Taper Log (web app)             │
│  steps · workouts · pace        meal checkmarks · weight          │
│  distance · active energy       free-text daily comments          │
│        │                               │                          │
│  [Shortcuts automation           [fetch() calls replace           │
│   POSTs JSON nightly]             localStorage]                   │
└────────┼───────────────────────────────┼──────────────────────────┘
         ▼                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                 INGESTION API — FastAPI (your stack)              │
│   POST /webhook/health     POST /log/meals    POST /log/comment  │
│   (HMAC-signed)            PUT  /log/weight                       │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     POSTGRES (single source of truth)             │
│  health_metrics · meal_logs · comments · plan_versions (JSONB)    │
│  agent_runs (audit) · recommendations · pending_approvals         │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       AGENT ORCHESTRATOR                          │
│  Triggers: ① nightly cron (daily review)  ② new comment event     │
│            ③ 6 PM cron (dinner/Swiggy window)                     │
│                                                                   │
│  LLM agent loop (tool use) with tools:                            │
│   get_day_context()        → today's logs + health + plan         │
│   log_offplan_food()       → structured entry from a comment      │
│   propose_plan_patch()     → JSON Patch + rationale (NOT applied) │
│   swiggy_mcp.*             → search restaurants/menus (READ-ONLY) │
│   create_recommendation()  → surfaces cards to you                │
│   notify_user()            → Telegram/WhatsApp message            │
└───────────┬─────────────────────────────┬────────────────────────┘
            ▼                             ▼
┌────────────────────────┐   ┌─────────────────────────────────────┐
│   GUARDRAIL LAYER      │   │   SWIGGY MCP PLATFORM (external)    │
│  deterministic Python, │   │  mcp.swiggy.com — Food/Instamart    │
│  not LLM:              │   │  tools. Prototype free localhost;   │
│  · kcal floor 1,600    │   │  production after approval.         │
│  · protein 120–150g    │   │  ⚠ Order-placing tools exist —      │
│  · deficit cap 500     │   │  your client whitelists SEARCH      │
│  · max ±15% change/day │   │  tools only. Ordering is            │
│  Big changes → HITL    │   │  structurally impossible, not       │
│  approval, not auto    │   │  just "prompted against".           │
└───────────┬────────────┘   └─────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DELIVERY — Telegram bot (v1)                   │
│  nightly digest · plan-change approvals (inline buttons)          │
│  Swiggy recommendation cards with macro reasoning                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer-by-Layer

### 2.1 Ingestion API (FastAPI + Pydantic)
Three write paths, all boring on purpose:

- **Auth (all endpoints):** every request carries `X-Api-Token`, a per-user credential minted by `python -m app.create_user`. Token → user row → `user_id` scopes every query; a wrong token gets a 401, and no endpoint can read or write another user's rows. HMAC signing remains the v2 upgrade.
- `POST /webhook/health` — receives the nightly Shortcuts payload: `{date, steps, active_kcal, workouts: [{type, distance_km, duration_min, avg_pace}]}`. The user's own token in the header identifies whose phone is pushing. Idempotent on `(user, date)` — re-sends upsert, never duplicate.
- `POST /log/meals`, `PUT /log/weight` — the V-Taper Log app stops writing to localStorage and calls these instead. (localStorage stays as offline fallback with sync-on-reconnect if you want the extra credit.)
- `POST /log/comment` — free text + date. Writing a comment **emits an event** (worker polls unprocessed rows every 30s) that wakes the agent. This is what makes it feel alive: you type "skipped lunch, ate 2 samosas at office instead", and within a minute the agent has responded. The tracker's floating 🤖 chat is a thin UI over this same pipe: after processing, the worker stamps `comments.agent_run_id`, and `GET /log/chat` returns the thread (comment + the run's output text) so the reply appears in-app as well as on Telegram. There is deliberately no separate/synchronous chat endpoint — one agent path, one audit trail.

### 2.2 Storage (Postgres)
**Everything is per-user.** A `users` table (name, api_token, telegram_chat_id, tz, lat/lng) anchors the system; every data table carries `user_id`, and natural keys are composite — `health_metrics (user_id, date)`, `meal_logs UNIQUE(user_id, date, meal_id)`, `weight_logs (user_id, date)`. A user's active plan is *their* latest approved `plan_versions` row.

The two design decisions that matter:

**Plans are versioned, never mutated.** `plan_versions(id, created_at, plan JSONB, patch JSONB, rationale TEXT, source, approved_by_user BOOLEAN)`. The active plan is just the latest approved row. Every agent modification is a JSON Patch (RFC 6902) against the previous version with a written rationale. You get: full audit trail, one-tap rollback, and a diff you can actually read ("dinner Wed: chilli chicken 650→560 kcal because lunch overshot").

**Agent runs are audited.** `agent_runs(id, trigger, input_context, tool_calls JSONB, output, tokens, cost, created_at)`. Every invocation logs what the agent saw, which tools it called with what arguments, and what it produced. When it does something dumb (it will), you debug from data, not vibes. This table is also your interview demo goldmine.

### 2.3 Agent Orchestrator — the actual "agentic" part
One agent, three triggers, five tools. Resist the multi-agent temptation — a single tool-using loop is correct at this scale. With multiple users, the cron triggers simply **fan out**: one isolated agent run per user (a failure for one user never blocks the others), and comments already carry their author. The critical safety property: the user is **never a tool parameter** — `tools.handle(user, ...)` injects `user_id` into every query, so the LLM cannot reach another user's data even if prompted to.

**Trigger ① — Nightly review (10 PM cron):** agent pulls the day's context — meals checked vs plan, health payload (did the walk happen? how far? what pace?), weight, any comments — and produces: (a) a day summary with real numbers, (b) tomorrow's adjustment *if warranted* (e.g., "you logged 16k steps + a 5km run today but only ate 1,600 kcal — add the optional dessert tomorrow, recovery matters"), (c) a Telegram digest.

**Trigger ② — Comment event:** the core NLU loop. Comment → agent classifies intent (`ate_offplan`, `skipped_meal`, `substituted`, `injury/soreness`, `schedule_change`, `craving`, `question`) → acts:
- *"had 2 samosas at office"* → `log_offplan_food(name="samosa", qty=2, est_kcal=520, est_protein=6)` → recalculates the day → "You're at 1,710 kcal with dinner pending. Swap tonight's phulkas for cucumber salad and you land on target."
- *"shoulder hurts from yesterday"* → `propose_plan_patch` swapping tomorrow's Push for Legs, rationale attached → goes to guardrails.
- *"cook didn't come today"* → triggers the Swiggy flow immediately with remaining macros.

**Trigger ③ — 6 PM Swiggy window:** computes remaining kcal/protein for the day → calls Swiggy MCP search tools (restaurants near you, dish-level menu data) → LLM estimates macros per candidate dish (menu data won't include macros — the agent estimates from dish name/description, and must present them as estimates) → ranks → pushes top 3 as cards: *"You have 640 kcal / 48g protein left. ① Tandoori chicken (half) + roti from X — est. 610 kcal, 52g P. ②…"*

**Framework choice:** Claude API (or OpenAI Agents SDK, per your learning plan) with native tool use, in a plain `while` loop with max-iterations. Skip LangChain/LangGraph for v1 — a hand-rolled loop over 5 tools is ~80 lines, fully debuggable, and demonstrates deeper understanding in interviews than framework plumbing.

### 2.4 Guardrail Layer — deterministic, not LLM
The most important architectural principle here: **the LLM proposes, Python disposes.**

Every `propose_plan_patch` passes through hard-coded validation *before* anything persists: daily kcal never below 1,600; protein stays 120–150g; deficit never exceeds 500 below TDEE; no single-day change >15%; training volume changes capped. Small compliant changes auto-apply with notification. Anything structural (rest-day insertion, calorie target change, multi-day rewrites) creates a `pending_approval` → Telegram message with **Approve / Reject** inline buttons. The plan is *yours*; the agent is staff, not boss.

The same principle governs Swiggy: the MCP client is initialized with a **whitelist of read/search tools only**. Order-placement tools are never registered with the agent, so "the agent accidentally ordered food" is impossible by construction — a much stronger guarantee than a system-prompt instruction, and exactly the kind of thing to say in an interview.

### 2.5 Delivery — Telegram first, plus the in-app chat
Telegram Bot API: free, no approval process, supports inline approval buttons, 20 lines of code. WhatsApp (Meta Cloud API) is the v2 upgrade — you already know that terrain from TableTruth, but its template-message rules and pricing are friction you don't need in week one.

Comment replies additionally surface inside the tracker's chat panel (`GET /log/chat`, polled while the panel is open) — same agent output, second screen. Approvals and the nightly digest remain Telegram-only: the digest is push (the app can't wake your phone), and approval buttons need to reach you when the app isn't open.

One bot serves all users: each user's DMs go to their own `telegram_chat_id` (stored in the users table), and an approval button press is honoured only if it comes from the plan owner's chat — the worker checks the presser's chat id and resolves the approval through the API using the owner's token, so ownership is enforced server-side in one place.

---

## 3. Infrastructure

- **Runtime:** one Docker Compose stack — `api` (FastAPI), `worker` (agent + APScheduler for the three cron triggers), `postgres`. No Celery/Redis needed at n=1 user.
- **Hosting:** Lightsail/EC2 t4g.small or Railway/Fly.io. Static outbound IP helps when Swiggy approves you for production.
- **IaC:** Terraform (your stack — do it for the portfolio even though it's one box).
- **Secrets:** env vars via SSM/Doppler — Anthropic/OpenAI key, Swiggy MCP credentials, Telegram token, webhook HMAC secret.
- **Cost reality:** LLM ~₹150–400/month at this usage (nightly run + a few comment events, use a cheap-tier model for classification and a strong one for plan patches), hosting ~₹400–800/month, Telegram free.

---

## 4. Build Order (each phase independently useful)

1. **Week 1 — Pipes:** FastAPI + Postgres + schema; Shortcuts automation POSTing health JSON; tracker app switched from localStorage to the API. *No AI yet.* You now own your data.
2. **Week 2 — Brain:** agent loop + nightly review + comment intent handling + Telegram digest. This is the demo-able core.
3. **Week 3 — Guardrails & plan versioning:** JSON Patch flow, validation layer, approve/reject buttons, agent_runs audit.
4. **Week 4 — Swiggy MCP:** register at mcp.swiggy.com/builders, prototype against their localhost tool schemas, wire search tools into the 6 PM trigger, ship recommendation cards.

---

## 5. Why This Is a Strong Portfolio Piece (be able to say this out loud)

It hits every checkbox for the AI Software Engineer role you're targeting, with zero ML math: **event-driven ingestion** (webhook from a physical device), **agentic tool-use loop** hand-built and auditable, **MCP integration** with a real production platform (Swiggy), **human-in-the-loop design** with deterministic guardrails around a probabilistic core, **versioned state with audit trails**, and your existing stack (FastAPI/Postgres/Docker/Terraform) doing the boring parts well. The one-line pitch: *"I built an agent that reads my Apple Health data and food logs, renegotiates my diet plan with me in natural language, and recommends macro-fitting Swiggy orders — with guardrails that make unsafe changes and accidental ordering structurally impossible."*
