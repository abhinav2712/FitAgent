from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import health_webhook, logs, plan, recommendations, me

app = FastAPI(title="FitAgent API", version="0.1.0")
app.include_router(health_webhook.router, tags=["ingestion"])
app.include_router(logs.router, tags=["ingestion"])
app.include_router(plan.router, tags=["plan"])
app.include_router(recommendations.router, tags=["recommendations"])
app.include_router(me.router, tags=["me"])

@app.get("/healthz")
def healthz():
    return {"ok": True}

# V-Taper Log tracker — the built SPA is served from the same origin as the API,
# so the app needs no CORS and one deploy covers both. Mounted last: API routes win.
# Missing dist/ (e.g. backend-only local dev) just means no UI, API still works.
web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
if web_dist.is_dir():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="tracker")
