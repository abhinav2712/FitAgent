# FitAgent 🏋️🤖

An agentic workflow that monitors my iPhone fitness data + daily meal check-ins,
understands free-text comments ("skipped lunch, had 2 samosas"), adapts my diet/training
plan within hard guardrails, and recommends macro-fitting Swiggy dishes — never orders.

**Stack:** FastAPI · Postgres · Anthropic tool-use loop (no framework) · React/Vite tracker ·
APScheduler · Telegram · Swiggy MCP · Docker Compose

## Quickstart
```bash
cp .env.example .env        # fill ANTHROPIC_API_KEY + TELEGRAM_BOT_TOKEN at minimum
docker compose up --build
# one command per person — creates the user, seeds their plan, prints their API token:
docker compose exec api python -m app.create_user "Abhi" --chat-id 123456789
open http://localhost:8000  # V-Taper Log tracker — paste the token in the pairing screen
# simulate the iPhone: see shortcuts/SHORTCUT_SETUP.md for a curl test payload
# leave a comment for the agent (or tap the floating 🤖 chat in the tracker):
curl -X POST localhost:8000/log/comment -H 'Content-Type: application/json' \
  -H 'X-Api-Token: <your token>' \
  -d '{"date":"2026-07-07","text":"skipped lunch, ate 2 samosas at office"}'
docker compose logs -f worker   # watch it get processed within 30s
```

## Multi-user
One deploy serves several people. `python -m app.create_user "<name>" --chat-id <id>`
mints a personal API token — it authenticates that person's tracker (pairing screen)
and their iPhone Shortcut (`X-Api-Token` header). Every row in Postgres carries a
`user_id`; the agent's cron triggers fan out per user; Telegram DMs go to each user's
own chat (one bot for all); approval buttons only work from the plan owner's chat.
The LLM never selects the user — Python injects the scope into every tool call.

## Tracker web app (`web/`)
The V-Taper Log is a React SPA built with Vite and baked into the Docker image —
FastAPI serves `web/dist` at `/`, so one server, one deploy, one HTTPS URL, zero CORS.
Meal check-offs, morning weight, and comments go straight to Postgres (the agent's
source of truth); off-plan food the agent logs from your comments shows up in the app.
Failed writes are queued in localStorage and replayed when you're back online.
The floating 🤖 button opens a chat with FitAgent — messages are comments, replies are
the worker's agent runs surfaced via `GET /log/chat` (same pipeline, same guardrails).
A Movement card shows steps + walking calories from the nightly iPhone Health sync.

```bash
cd web && npm install && npm run dev   # frontend dev server :5173, proxies API to :8000
npm run build                          # → web/dist (what FastAPI serves)
```

Docs: [Agent Capabilities](docs/CAPABILITIES.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Implementation Plan](docs/IMPLEMENTATION_PLAN.md) · [Coding Guidelines](docs/CODING_GUIDELINES.md) ·
[Future Features](docs/FUTURE_FEATURES.md) · [iPhone Shortcut Setup](shortcuts/SHORTCUT_SETUP.md) ·
[CLAUDE.md](CLAUDE.md)
