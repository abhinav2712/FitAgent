# iPhone Shortcut Setup (~30 min, no code)

Goal: every night at 9:30 PM your iPhone POSTs the day's Health data to FitAgent.
Each person builds this on their own phone with their own API token — that's how
the server knows whose data is arriving.

## Build the Shortcut
1. Shortcuts app → + → name it "FitAgent Sync"
2. Add action **Find Health Samples** → type: Steps, today → **Calculate Statistics** (Sum) → save to variable `steps`
3. Repeat for **Active Energy** → variable `activeKcal`
4. Add **Find Workouts** where date is today → for the first workout, get Distance and Duration → variables `dist`, `dur`
5. Add **Get Contents of URL**:
   - URL: `https://YOUR-SERVER/webhook/health`
   - Method: POST · Request Body: JSON
   - Headers: `X-Api-Token` = **your personal token** (printed by
     `python -m app.create_user "<your name>"` — same one the tracker's pairing screen uses)
   - JSON body:
     ```
     date: <Current Date, format yyyy-MM-dd>
     steps: <steps>
     active_kcal: <activeKcal>
     workouts: [{ "type": "walk", "distance_km": <dist>, "duration_min": <dur> }]
     ```
6. Run it once manually → check `docker compose logs api` shows a 200.

## Automate it
Shortcuts → Automation → + → Time of Day → 9:30 PM daily → Run "FitAgent Sync"
→ turn OFF "Ask Before Running".

## Test payload (no phone needed)
```bash
curl -X POST http://localhost:8000/webhook/health \
  -H "Content-Type: application/json" -H "X-Api-Token: <your token>" \
  -d '{"date":"2026-07-07","steps":9412,"active_kcal":410,
       "workouts":[{"type":"walk","distance_km":5.1,"duration_min":52,"avg_pace_min_per_km":10.2}]}'
```

Note: Shortcuts' Health access covers steps/workouts/energy well but not full GPS
routes. If you later want route-level data, the Health Auto Export app (~₹500)
POSTs richer payloads to the same webhook — the API doesn't need to change.
