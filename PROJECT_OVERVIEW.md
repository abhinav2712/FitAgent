# FitAgent — Project Overview

### One line
A personal AI agent that watches my real life — steps from my iPhone, meals I check off, comments I type — and keeps my fat-loss plan honest: adapting it within hard safety rails and recommending macro-fitting Swiggy dinners, without ever placing an order.

---

## The Problem

Every fitness plan dies the same death: contact with reality. The plan says tandoori chicken; the cook doesn't show up. The plan says push day; the shoulder is sore. The plan says 1,850 kcal; two samosas happened at the office. Traditional tracking apps make *me* do the reconciliation work — recount calories, rebalance the day, decide what to change — which is exactly the friction that kills the habit by week three.

The insight: the data already exists. My iPhone knows my steps, distance, and pace. My tracker app knows what I ate and skipped. The only missing piece is something that *reads all of it, understands a sentence like "skipped lunch, had 2 samosas," and does the arithmetic and re-planning for me.* That's not an app feature — that's an agent.

## The Solution

FitAgent is a personal agentic system (one deploy serves me and the few people I set it up for — each with their own token, plan, data, and Telegram thread) with three jobs:

**1. It watches.** Every night my iPhone pushes the day's Health data (steps, walks, runs, pace) to my server via an Apple Shortcut — no manual entry, no wearable subscription. My web tracker (V-Taper Log) sends meal check-offs, morning weight, and free-text comments as I go.

**2. It understands and adapts.** An LLM agent with tools wakes up on three triggers — a nightly review, any new comment, and a 6 PM dinner window. It interprets comments in plain language, logs off-plan food with estimated macros, rebalances the rest of the day, and when a real plan change is warranted (injury, schedule change, consistent under-eating), it *proposes* the change as a structured patch with a written rationale. Deterministic guardrails validate every proposal — calories can never drop below 1,600, protein stays 120–150g, no wild single-day swings — and anything structural comes to me as a Telegram message with Approve/Reject buttons. The agent is staff, not boss.

**3. It recommends, never orders.** When dinner needs to come from outside (cook absent, travel, craving), the agent computes my *remaining* calories and protein for the day, searches nearby dishes through Swiggy's MCP platform, and sends me the top 3 with estimated macros and one-line reasoning. Ordering is structurally impossible: the Swiggy client whitelists search tools only — order and cart tools are never even registered with the agent.

## A Day With FitAgent

- **6:00 AM** — lake walk. The iPhone records it; I do nothing.
- **1:30 PM** — I type: *"skipped lunch, ate 2 samosas at office."* Thirty seconds later, Telegram: *"Logged ~520 kcal. You're at 1,180 with dinner pending — swap tonight's phulkas for salad and you land on target."*
- **6:00 PM** — cook didn't come. Telegram: *"You have 640 kcal / 48g protein left. ① Tandoori chicken (half) + roti from Grill Nation — est. 610 kcal, 52g P…"*
- **10:00 PM** — nightly digest: real numbers, streak status, and — only if warranted — one proposed adjustment for tomorrow, awaiting my tap.

## What Makes the Design Interesting

- **The LLM proposes, Python disposes.** Every plan mutation is an RFC 6902 JSON Patch validated by hard-coded guardrails before persisting. The model cannot talk its way past a calorie floor.
- **Safety by construction, not by prompt.** "Don't order food" isn't an instruction the model might ignore — order tools simply don't exist in its tool registry.
- **Append-only, fully audited.** Plans are versioned with patch + rationale (one-tap rollback); every agent run logs its full tool-call trace. When the agent does something dumb, I debug from data.
- **Event-driven from a physical device.** Apple Health has no cloud API, so the phone pushes — a real-world integration constraint most tutorial projects never touch.
- **No framework theater.** The agent is an ~80-line hand-rolled tool-use loop. Five tools, three triggers, a handful of users (one isolated run each — the LLM never selects the user; Python injects the scope). Complexity is spent on guardrails and auditability, not orchestration plumbing.

## Stack

FastAPI · PostgreSQL · Anthropic API (tool use) · Swiggy MCP · APScheduler · Telegram Bot API · Apple Shortcuts · Docker Compose · Terraform on AWS

## Status & Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Data pipes: health webhook, meal/comment API, iPhone Shortcut, deploy | ⬜ |
| 2 | Agent brain: comment understanding, nightly review, Telegram digest | ⬜ |
| 3 | Guardrails: plan versioning, validation, human-in-the-loop approvals | ⬜ |
| 4 | Swiggy MCP: live dish search + recommendation cards (mock works today) | ⬜ |
| v2 ideas | WhatsApp delivery · GPS route analysis via Health Auto Export · weekly trend reports · gym progressive-overload tracking — full backlog: [docs/FUTURE_FEATURES.md](docs/FUTURE_FEATURES.md) | — |

## Why This Project Exists (honestly)

Two reasons, and both are real. First, I'm actually cutting from 76kg to 68kg and the friction problem above is mine. Second, I'm building toward AI Software Engineer roles — and this is deliberately the shape of production agentic work: event ingestion from the physical world, an auditable tool-use loop, deterministic guardrails around a probabilistic core, MCP integration with a live commercial platform (Swiggy), and human-in-the-loop control. It's a system I ship, live inside of daily, and can defend line-by-line in an interview.
