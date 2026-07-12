Here's the full local runbook, in order:

1. One-time setup — .env

cd ~/Desktop/fitagent
cp .env.example .env
Fill the LLM section — two options:

FREE LOCAL (no credits, currently active in .env): Ollama serves an Anthropic-compatible API on this Mac.
  brew services start ollama          # or: ollama serve
  ANTHROPIC_API_KEY=ollama, ANTHROPIC_BASE_URL=http://host.docker.internal:11434,
  AGENT_MODEL=gemma4:e4b (already pulled; any tool-calling model works, e.g. qwen3:8b).
  Trade-off: a local 8B model is far weaker than Claude — expect clumsier replies and
  occasional malformed patches. The guardrails are deterministic Python, so safety is
  identical; only quality differs. Swap to paid Claude anytime by editing .env.

PAID (better quality): ANTHROPIC_API_KEY from console.anthropic.com, leave ANTHROPIC_BASE_URL empty.

TELEGRAM_BOT_TOKEN — optional for local testing (empty = notifications print to worker logs).
For real use: message @BotFather → /newbot → copy the token. Chat ids are per user — each person messages the bot once, then https://api.telegram.org/bot<TOKEN>/getUpdates shows their chat.id; pass it to create_user below.
Leave SWIGGY_MOCK=true (real MCP isn't implemented yet) and DATABASE_URL as-is (it points at the db compose service).

2. Start the stack

docker compose up --build
That builds the React tracker (node stage), bakes it into the API image, and starts three containers: db (Postgres, schema auto-applied), api (:8000), worker (scheduler + Telegram polling). First build takes a few minutes.

Then create each user — one command per person; it seeds their plan and prints their personal API token (save it!):


docker compose exec api python -m app.create_user "Abhi" --chat-id 123456789
docker compose exec api python -m app.create_user "Friend" --chat-id 987654321
3. Use it — the whole loop
Open http://localhost:8000 — that's the V-Taper Log, served by FastAPI itself.
First visit shows a pairing screen: paste your API token (each person pastes their own on their own phone/browser). The same token goes in that person's iPhone Shortcut as the X-Api-Token header.

Then walk the flow end to end:

Check off a meal / enter weight in the Today tab → lands in Postgres immediately.
Tap the floating 🤖 button and chat: "skipped lunch, ate 2 samosas at office" → within ~30s the worker picks it up, the agent logs the samosas as an off-plan row, the reply appears in the chat (and on Telegram), and your plate + fuel gauges refresh with the rebalanced day. Watch it think:

docker compose logs -f worker
Simulate the iPhone (the health webhook, normally sent by the Shortcut at 9:30 PM):

curl -X POST localhost:8000/webhook/health \
  -H 'Content-Type: application/json' -H "X-Api-Token: <your token>" \
  -d '{"date":"2026-07-07","steps":12400,"active_kcal":410,"workouts":[{"type":"walk","distance_km":5.1,"duration_min":52}]}'
(refresh the tracker — the Movement card now shows the steps + walking calories)
Trigger the scheduled runs manually instead of waiting for 22:00 / 18:00 IST:

docker compose exec worker python -c "from worker.scheduler import nightly_all; nightly_all()"   # all users
docker compose exec worker python -c "from worker.scheduler import swiggy_all; swiggy_all()"    # mock Swiggy dinner picks, all users
Test the approval flow: comment "my shoulder hurts, swap tomorrow's push day" → Telegram message with ✅/❌ buttons → tap Approve → new row in plan_versions.
Debug from data — every agent run is audited:

docker compose exec db psql -U fitagent -c "SELECT id, trigger, output_text FROM agent_runs ORDER BY id DESC LIMIT 3;"
4. Frontend dev mode (only when editing the UI)

cd web && npm install && npm run dev   # hot-reload UI at :5173, API calls proxied to :8000
The Docker stack keeps serving the last built version at :8000; npm run build refreshes what FastAPI serves (or just rebuild the image).

5. Tests

docker compose exec api pytest tests/ -v   # guardrail tests — the critical ones
Shut down with docker compose down (data survives in the pgdata volume; down -v wipes it).

One heads-up: without TELEGRAM_BOT_TOKEN (or a user without --chat-id) notifications no-op into the worker logs — replies still appear in the tracker's 🤖 chat, which is enough for local testing. In free local mode the first reply after a cold start is slow (~30–60s: Ollama loads the model into RAM), then speeds up. Setting up for someone else = one create_user command + they pair their browser + build their Shortcut with their token.