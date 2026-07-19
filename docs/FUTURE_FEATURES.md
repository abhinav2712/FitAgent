# FitAgent — Future Features & Ideas

Idea backlog for evolving the agentic workflow. Nothing here is committed work.
Every idea must respect the invariants (CLAUDE.md): the LLM proposes / Python
disposes, Swiggy stays read-only, plans stay append-only, user scoping stays
code-injected — and complexity must be earned (CODING_GUIDELINES §8).

Effort: **S** = an evening · **M** = a weekend · **L** = a week+

---

## 1. Track more of real life (data in)

| Idea | What & why | How it fits | Effort |
|---|---|---|---|
| **Sleep data** | Shortcut already reads Health — add sleep hours/quality to the nightly payload. Recovery is the missing variable in "should tomorrow be push or rest?" | New columns on `health_metrics`; agent context gains a `sleep` field; workout-swap proposals get smarter | S |
| **Waist & body measurements** | The goal is literally a V-taper — weight alone can't see recomposition. Weekly waist/chest/shoulder entries | New `measurements` table + tracker card + trend chart; nightly review references the ratio | S |
| **Gym progressive overload** | Log sets × reps × weight per exercise (the tracker already has the exercise list). Agent suggests next session's weights: "you hit 3×15 at 5kg twice — go 7.5kg" | New `workout_logs` table; suggestions are *advice in the digest*, never auto-changing the plan | M |
| **Meal photos → macro estimates** | Snap a plate in the chat; a vision call estimates the dish + macros, logs it as off-plan ("est.") after you confirm. The highest-leverage friction-killer | Image upload on `/log/comment`; vision model call in the comment flow; estimate confirmed via chat before logging | M |
| **GPS routes & pace trends** (v2 list) | Health Auto Export app pushes route-level data to the same webhook. Enables "your 5km pace improved 40s this month" | Webhook already tolerates richer payloads (`raw_payload` JSONB); add parsing + a pace trend in Progress | M |
| **Pantry / cook-schedule awareness** | "Cook is off Thursdays" or "no eggs this week" as standing context, so rebalancing suggests feasible meals | A per-user `context_notes` table the agent reads in `get_day_context`; user-editable, agent proposes additions via approval | M |

## 2. A smarter brain (agent behaviors)

| Idea | What & why | How it fits | Effort |
|---|---|---|---|
| **Weekly trend review** (v2 list) | Sunday-night run: weight trend vs. intake math, adherence %, plateau detection, at most one structural proposal (e.g. refeed day) | Fourth cron trigger; same loop, new prompt; structural proposals already route to approval | S |
| **Deterministic TDEE estimation** | Estimate true TDEE from weight trend + logged intake (3-week rolling window) — *in Python, not the LLM* — and feed it into agent context. Unlocks the "deficit cap 500 below TDEE" guardrail that ARCHITECTURE.md promised but was never implemented | New pure function beside guardrails; new guardrail check; needs consistent weight logging first | M |
| **Cheap-model intent triage** | `classifier_model` (Haiku) exists in config but is unused. Classify comments first; only plan-affecting intents go to the strong model. Cuts cost ~5–10× on chit-chat | One classification call before `loop.run`; log both models' usage in `agent_runs` | S |
| **Food preference memory** | "I hate lauki" should stick. Agent proposes preference notes; you approve; future meal swaps respect them | Same `context_notes` table as above; append-only with approval — the agent never silently rewrites what it knows about you | M |
| **Proactive nudges (carefully)** | No lunch logged by 3 PM → one gentle ping. Strictly rate-limited — notification fatigue kills trust faster than missed macros | New cron; per-user daily nudge budget enforced in Python | S |
| **Agent eval harness** | `agent_runs` already stores every input + tool trace — that's a regression dataset. Replay recorded scenarios against prompt changes and diff the tool calls before shipping a prompt tweak | Offline script; zero prod risk; the single best guard for "did my prompt edit break the samosa flow?" | M |

## 3. Better interaction (delivery & UX)

| Idea | What & why | How it fits | Effort |
|---|---|---|---|
| ~~**Plan history screen**~~ ✅ shipped | `GET /plan/history` + the "Plan history" card in the Progress tab: versions, patches, rationales, approval state | Read-only endpoint over `plan_versions`; append-only design made this free | S |
| **Instant chat pickup** | Postgres LISTEN/NOTIFY instead of the 30s comment poll — replies in ~2s. Only when the latency actually annoys (earn-it table) | Worker listens; API `NOTIFY`s on comment insert | S |
| **Voice notes** | Speak instead of type after a workout; transcribe → normal comment pipeline | Audio upload + transcription call in front of `/log/comment`; everything downstream unchanged | M |
| **WhatsApp delivery** (v2 list) | Meta Cloud API instead of/alongside Telegram — where the rest of life already happens | `notify.py` grows a second transport behind the same `send(user, ...)` signature | M |
| **PWA + push notifications** | Install the tracker to the home screen; digest arrives as a push even with the app closed | Manifest + service worker; web-push keys; replaces nothing, adds a channel | M |
| **Weekly report card** | A shareable one-page summary (weight trend, adherence, streak, PRs) rendered from real data every Sunday | Server-rendered HTML route or Telegram image; feeds off the weekly trend review | M |

## 4. Food ecosystem

| Idea | What & why | How it fits | Effort |
|---|---|---|---|
| ~~**Real Swiggy MCP**~~ ✅ client shipped | Streamable-HTTP client + per-user OAuth linker (`app.swiggy_auth`) + whitelist tests. Remaining: each user links once (phone+OTP) and flips SWIGGY_MOCK=false; token re-link every ~5 days until Swiggy ships refresh tokens | Whitelist enforced by `_assert_allowed` before every call; user lat/lng passed from users table | M |
| **Dish macro cache** | Once real menus flow: cache the agent's macro estimates per (restaurant, dish) so repeat recommendations are consistent and cheaper | New table keyed on restaurant+dish; estimates still labelled "est." | S |
| **Instamart meal-prep list** | Sunday trend review outputs next week's grocery list matching the plan (read-only recommendation, like dishes) | Same MCP whitelist principles — search only | M |

## 5. Platform & robustness

| Idea | What & why | How it fits | Effort |
|---|---|---|---|
| **HMAC request signing + token rotation** | The documented v2 security upgrade — required before exposing beyond the trusted circle | `security.py`; per-user secrets already have a home in the users table | M |
| **Per-user timezones & schedules** | When someone outside IST actually joins (earn-it trigger). `users.tz` column already exists, waiting | Per-user cron jobs or a minute-tick scheduler checking each user's local time | M |
| **Cost dashboard** | `agent_runs` has tokens per run — a small `/admin/costs` view or weekly Telegram line: "this week: ₹41" | Read-only aggregation; keeps the ₹150–400/month promise honest | S |
| **Admin CLI** | `python -m app.admin list-users / rotate-token <id> / disable <id>` — the ops you'll want the day a token leaks | Small argparse module beside `create_user` | S |
| **Backups + restore drill** | Nightly `pg_dump` to S3 is in the deploy plan — add a documented, *tested* restore path. Body data deserves a fire drill | One script + one doc section; run the drill once | S |

---

## Non-goals (deliberately never)

- **Placing orders, ever** — recommendation-only is the design, not a missing feature.
- **Multi-agent orchestration / frameworks** — one auditable loop is the point.
- **Coaching below the guardrail floors** — no feature will make 1,200 kcal/day reachable.
- **Public SaaS** — multi-user means "people I personally set up," not sign-ups. Auth,
  rate limiting, and liability are a different product.
- **Medical claims** — trends and arithmetic, not diagnoses.

## Suggested picking order

Cheap wins that compound first: ~~plan history screen~~ (✅ shipped) → **intent triage →
weekly trend review → sleep data → waist measurements**. Then the two bigger bets that
most change daily life: **meal photos** and **real Swiggy MCP** (approval-gated).
Everything in §5 rides along with the deployment milestone.
