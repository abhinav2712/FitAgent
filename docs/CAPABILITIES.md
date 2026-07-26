# FitAgent — What the Agent Can and Cannot Do

The user-facing contract. Every claim here is enforced in code (guardrails,
tool whitelist, approval flow), not by prompt-engineering hope. If you change
behavior in code, change this file in the same commit.

---

## What it does, by trigger

### 💬 When you message it (🤖 chat in the tracker, picked up within ~5s and streamed live)
- **Understands plain language**: "skipped lunch, ate 2 samosas at office",
  "shoulder hurts, swap tomorrow's push day", "cook didn't come", "what should
  I eat tonight to hit my protein?"
- **Logs off-plan food** with estimated macros → appears in your plate as an
  "Off-plan · logged by agent" row and counts toward your fuel gauge.
- **Records day notes** for non-food deviations ("rest-day walk skipped — 20 min
  yoga instead") → shown as the 🤖 Today's notes card on the Today tab. These are
  the reality layer, like off-plan food — never a plan change.
- **Rebalances the rest of *today***: recalculates what you have left and either
  advises ("swap tonight's phulkas for salad") or edits today's remaining meals
  within the guardrail bounds below. It touches future days only when genuinely
  warranted (injury, schedule change), and prefers the smallest change.
- **Answers questions** about your numbers using your real logged data.
- Replies land in the chat **and** your Telegram DM.

### 🌙 Nightly review (22:00)
- A digest with real numbers: kcal + protein eaten vs target, steps, workout done.
- At most **one** proposed adjustment for tomorrow, only if warranted
  (e.g. big activity day + undereating → add the optional dessert back).

### 🍽 Dinner window (18:00) & on-demand food picks
- Computes your **remaining** kcal/protein for the day, searches Swiggy Food, and
  saves the top 3 dishes — restaurant, price, estimated macros (always "est."),
  one-line reasoning. Appears as the **Swiggy picks card** on your Today tab
  (and on Telegram if configured).
- Ask anytime in chat ("what should I order right now") — same flow, same card.
- If you have <300 kcal left, it recommends *not* ordering.

### 🛒 Instamart — snacks to stock up on (on-demand)
- Ask for pantry items, not a single meal: "what healthy snacks should I stock
  up on", "recommend high-protein things to keep at my desk". The agent
  searches Instamart and saves up to 3 picks — brand, pack size, price,
  estimated macros — on a separate **Instamart card**.
- Same guardrails as Food: read-only search, "est." macros, no ordering.

Live searches on both services anchor to your **most-recent saved Swiggy
delivery address** (looked up read-only — the agent can never add or delete
addresses, and your full address text never enters the model's context, only
an opaque id). Mock catalog until you link your Swiggy account
(`python -m app.swiggy_auth <user id>`, one-time phone+OTP; token lasts ~5
days, no refresh — re-link on expiry). Live or mock, ordering stays
structurally impossible for both services.

---

## The permission model — who decides what

| Action | Who decides | Enforced where |
|---|---|---|
| Log off-plan food you mention | Agent, automatic | appends to your log only — never touches the plan or goals |
| Small meal tweaks (≤4 edits, today's items) | Agent auto-applies, you're notified | `guardrails.apply_and_validate` bounds below |
| **Your goals/targets (kcal, protein)** | **You, always** — Approve/Reject in the tracker's Today-tab card or on Telegram | any patch touching `/targets` or `/weekly_workouts` requires approval (`requires_human_approval`) |
| Weekly workout schedule | You, always (same buttons) | same |
| Changing the guardrail constants themselves | Only you, asking a human explicitly in code | hard-coded in `guardrails.py`; agent suggestions are not authorization |
| Rolling back any plan change | You | plans are append-only versions — every change has a patch + rationale, one-tap revert |

## Hard limits — impossible by construction, not by instruction

- **Never places an order.** Both Swiggy clients (Food and Instamart) whitelist
  search tools only; cart/order/checkout/address-mutation tools are never
  registered with the agent, on either service.
- **Never drops a day below 1,600 kcal**, never sets protein outside
  **120–150g**, never swings a single day's calories more than **±15%** —
  validation runs *before* anything persists, and it fails closed.
- **Never edits history.** Plans are append-only versions; logs are your data.
- **Never sees another user's data.** Your user id is injected by the server
  from your API token into every query — it is not a parameter the model can set.
- **Fully audited.** Every run writes an `agent_runs` row: what it saw, every
  tool call with arguments, what it produced, token cost. Debuggable from data.

## Current limitations (honest list)

- The worker picks up a new message within ~5s, then the reply streams in
  live (word-by-word, plus "checking your day" / "logging that" style
  progress) while the panel is open. If the panel wasn't open or the
  connection dropped, the finished reply still appears on the next
  reconciliation poll — nothing is lost, only the live typing effect is missed.
- Swiggy results are mock dishes/items until you link your Swiggy account.
- Live search (Food and Instamart alike) needs at least one saved delivery
  address on your Swiggy account (the agent looks it up, read-only — it never
  adds one for you).
- Nightly/dinner crons run in one shared timezone (`USER_TZ`) for all users.
- Macro numbers for restaurant food are estimates — treated and labelled as such.
- Exercise check-offs in the tracker are device-local; the agent reads your
  workouts from iPhone Health data instead.
