# FitAgent — What the Agent Can and Cannot Do

The user-facing contract. Every claim here is enforced in code (guardrails,
tool whitelist, approval flow), not by prompt-engineering hope. If you change
behavior in code, change this file in the same commit.

---

## What it does, by trigger

### 💬 When you message it (🤖 chat in the tracker, ~30s reply)
- **Understands plain language**: "skipped lunch, ate 2 samosas at office",
  "shoulder hurts, swap tomorrow's push day", "cook didn't come", "what should
  I eat tonight to hit my protein?"
- **Logs off-plan food** with estimated macros → appears in your plate as an
  "Off-plan · logged by agent" row and counts toward your fuel gauge.
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

### 🍽 Dinner window (18:00)
- Computes your **remaining** kcal/protein for the day, searches Swiggy
  (mock until Builders Club approval), and sends the top 3 dishes with
  estimated macros — always labelled "est." — and one-line reasoning.
- If you have <300 kcal left, it recommends *not* ordering.

---

## The permission model — who decides what

| Action | Who decides | Enforced where |
|---|---|---|
| Log off-plan food you mention | Agent, automatic | appends to your log only — never touches the plan or goals |
| Small meal tweaks (≤4 edits, today's items) | Agent auto-applies, you're notified | `guardrails.apply_and_validate` bounds below |
| **Your goals/targets (kcal, protein)** | **You, always** — Approve/Reject buttons on Telegram | any patch touching `/targets` or `/weekly_workouts` requires approval (`requires_human_approval`) |
| Weekly workout schedule | You, always (same buttons) | same |
| Changing the guardrail constants themselves | Only you, asking a human explicitly in code | hard-coded in `guardrails.py`; agent suggestions are not authorization |
| Rolling back any plan change | You | plans are append-only versions — every change has a patch + rationale, one-tap revert |

## Hard limits — impossible by construction, not by instruction

- **Never places an order.** The Swiggy client whitelists search tools only;
  cart/order/checkout tools are never registered with the agent.
- **Never drops a day below 1,600 kcal**, never sets protein outside
  **120–150g**, never swings a single day's calories more than **±15%** —
  validation runs *before* anything persists, and it fails closed.
- **Never edits history.** Plans are append-only versions; logs are your data.
- **Never sees another user's data.** Your user id is injected by the server
  from your API token into every query — it is not a parameter the model can set.
- **Fully audited.** Every run writes an `agent_runs` row: what it saw, every
  tool call with arguments, what it produced, token cost. Debuggable from data.

## Current limitations (honest list)

- Replies take up to ~30s (worker polls comments on that interval).
- Swiggy results are mock dishes until mcp.swiggy.com/builders approval.
- Nightly/dinner crons run in one shared timezone (`USER_TZ`) for all users.
- Macro numbers for restaurant food are estimates — treated and labelled as such.
- Exercise check-offs in the tracker are device-local; the agent reads your
  workouts from iPhone Health data instead.
