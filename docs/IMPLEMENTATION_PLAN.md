# FitAgent — Implementation Plan
### Ordered steps, each phase independently useful. Do them in order; don't skip to the fun part.

---

## Phase 0 — Accounts & Keys (1 evening, do all of it now)

| # | Step | Output |
|---|------|--------|
| 0.1 | Create Telegram bot: message **@BotFather** → `/newbot` → name it | `TELEGRAM_BOT_TOKEN` |
| 0.2 | Each person messages the bot once, then hit `https://api.telegram.org/bot<TOKEN>/getUpdates` — copy their `chat.id` | per-user chat id (pass to `create_user --chat-id`) |
| 0.3 | Anthropic Console → create API key (₹500 credit lasts weeks at this usage) | `ANTHROPIC_API_KEY` |
| 0.4 | Register at **mcp.swiggy.com/builders** (localhost prototyping is free, production needs approval — apply NOW, approval takes time) | Swiggy MCP access pending |
| 0.5 | `cp .env.example .env` and fill everything above | working `.env` |
| 0.6 | Per person: `docker compose exec api python -m app.create_user "<name>" --chat-id <id>` (after Phase 1 step 1) | their personal API token (tracker pairing + Shortcut header) |

---

## Phase 1 — Own Your Data Pipes (Week 1) · *no AI yet, on purpose*

**Goal:** every data source lands in Postgres reliably before any agent exists.

1. `docker compose up --build` → confirm `GET localhost:8000/healthz` returns ok.
2. `docker compose exec api python -m app.create_user "<name>"` per person → confirm `GET /plan/active` (with the printed `X-Api-Token`) returns the plan JSON, and the tracker's pairing screen accepts the token.
3. Test the health webhook with the curl payload in `shortcuts/SHORTCUT_SETUP.md` (with your token) → row appears in `health_metrics` for your user.
4. **Deploy** (see Phase 5 checklist) — the Shortcut needs a public URL, so deploy early.
5. Build the iPhone Shortcut per `shortcuts/SHORTCUT_SETUP.md`, point it at the deployed URL, set the 9:30 PM automation. Verify two consecutive nights of data.
6. ✅ Done — the V-Taper Log lives in `web/` (React/Vite, served by FastAPI): checkbox toggles → `POST /log/meals`, weight → `PUT /log/weight`, floating 🤖 chat → `POST /log/comment` (replies via `GET /log/chat`), Movement card ← health webhook data. localStorage is the offline write queue.

**Definition of done:** 3 consecutive days where steps, meals, and weight all appear in Postgres without you touching a terminal.

---

## Phase 2 — The Agent Brain (Week 2)

**Goal:** comments get understood and acted on; nightly digest arrives on Telegram.

1. Read `agent/loop.py` end to end — it's ~80 lines and it IS the project. Understand it before running it.
2. Run the worker locally, then message the agent (tracker's 🤖 chat or `POST /log/comment`): `"skipped lunch, ate 2 samosas at office"` → within 30s the reply appears in the chat and on Telegram, with the rebalanced day. Inspect the `agent_runs` row: read `tool_calls` to see exactly what it did.
3. Tune `agent/prompts.py` against your real comment style for a few days. Add intent examples for things you actually write.
4. Verify the nightly review fires at 22:00 IST (or trigger manually: `docker compose exec worker python -c "from agent.loop import nightly_review; nightly_review()"`).
5. Cost check after 3 days: `SELECT trigger, sum(tokens_in), sum(tokens_out) FROM agent_runs GROUP BY 1;`

**Definition of done:** one full week where you never open the database but always know your numbers — because the agent told you.

---

## Phase 3 — Guardrails & Plan Evolution (Week 3)

**Goal:** the agent can safely change the plan; you can approve/reject from Telegram.

1. `pytest tests/ -v` — the guardrail tests must pass before anything else. Add a test for every new rule you invent.
2. Post a comment that warrants a plan change: `"my shoulder hurts, swap tomorrow's push day"` → expect a Telegram message with ✅/❌ buttons → tap Approve → confirm a new approved `plan_versions` row with the patch and rationale.
3. Try to break it: comment `"cut my calories to 1200 I want to go faster"` → the agent may propose; the guardrail MUST reject (kcal floor 1600). This test failing is a stop-everything bug.
4. ✅ Done — `GET /plan/history` returns versions + patches + rationales + approval state, rendered as the "Plan history" card in the tracker's Progress tab.

**Definition of done:** you can show someone the plan's version history and say "the agent proposed these, here's what got rejected and why."

---

## Phase 4 — Swiggy Recommendations (Week 4)

**Goal:** 6 PM Telegram message with 3 dishes that fit your remaining macros.

1. Runs day one with `SWIGGY_MOCK=true` — the mock dishes exercise the full flow (remaining-macro math → ranking → recommendation cards). Verify this first.
2. Once Builders Club approves you: implement the real connection in `agent/swiggy_mcp.py` against their MCP tool schemas. **The `ALLOWED_TOOLS` whitelist stays search-only — this is the load-bearing safety property. Never register cart/order tools.**
3. Add dish-macro estimation guidance to the SWIGGY prompt (Indian restaurant portions run large; the agent should estimate conservatively and always label numbers "est.").
4. Quality pass for a week: were the recommendations actually orderable, nearby, and macro-sane? Tune.

**Definition of done:** on a day the cook doesn't come, the 6 PM message alone is enough to decide dinner.

---

## Phase 5 — Deployment Checklist (do during Phase 1, step 4)

**What gets deployed:** one VM running the whole `docker compose` stack (db + api + worker). At n=1 user, this is correct — resist Kubernetes.

1. **Provision:** AWS Lightsail ($5, 1GB) or EC2 t4g.small — Ubuntu 24.04. (Railway/Fly.io work too if you'd rather skip server admin, but the VM is better Terraform practice.)
2. **Terraform it** (portfolio points): instance + static IP + security group allowing 22, 80, 443 only.
3. Install Docker + compose plugin; clone repo; `cp .env.example .env` and fill with production values; `docker compose up -d --build`; seed the plan.
4. **HTTPS:** point a subdomain (e.g. `fit.yourdomain.in`) at the static IP; run **Caddy** in front (2-line Caddyfile, automatic Let's Encrypt) proxying :443 → api:8000. iPhone Shortcuts is happiest with clean HTTPS.
5. **Persistence & restart:** the compose file already has `restart: unless-stopped` semantics via Docker defaults — add `restart: unless-stopped` to all three services; pgdata is a named volume so DB survives redeploys.
6. **Backups:** nightly `pg_dump` to S3 (one cron line). Your body data deserves a backup.
7. **Monitoring (minimal):** UptimeRobot ping on `/healthz` + a "worker heartbeat" — the nightly digest itself is your liveness check; if it doesn't arrive by 22:15, something is down.

---

## Sequencing Rules (why this order)

Pipes before brains (Phase 1 before 2) because an agent reading an empty database produces confident nonsense. Guardrails before Swiggy (3 before 4) because plan-mutation safety matters more than recommendations. Deploy inside Phase 1, not at the end, because the iPhone Shortcut — your only involuntary data source — needs a public URL from day 3, and a system you don't have to remember to feed is the only kind you'll still be using in month 3.
