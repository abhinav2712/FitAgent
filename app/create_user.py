"""Create a user, mint their API token, and seed their plan v1. Run per person:
    python -m app.create_user "Abhi" --chat-id 123456789
    python -m app.create_user "Priya" --tz Asia/Kolkata --lat 12.93 --lng 77.61

Prints the token once — it goes into the tracker's pairing screen AND the
iPhone Shortcut's X-Api-Token header. Re-running with the same name creates a
NEW user (names aren't unique); look tokens up with:
    SELECT id, name, api_token FROM users;
"""
import argparse
import json
import secrets
from sqlalchemy import text
from app.db import SessionLocal
from app.seed_plan import PLAN_V1

def main():
    p = argparse.ArgumentParser(description="Create a FitAgent user + seed plan v1")
    p.add_argument("name")
    p.add_argument("--chat-id", default=None, help="Telegram chat id for this user's DMs")
    p.add_argument("--tz", default="Asia/Kolkata")
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lng", type=float, default=None)
    args = p.parse_args()

    token = secrets.token_hex(24)
    db = SessionLocal()
    try:
        user_id = db.execute(text("""
            INSERT INTO users (name, api_token, telegram_chat_id, tz, lat, lng)
            VALUES (:n, :t, :c, :tz, :lat, :lng) RETURNING id
        """), {"n": args.name, "t": token, "c": args.chat_id,
               "tz": args.tz, "lat": args.lat, "lng": args.lng}).first()[0]
        db.execute(text("""
            INSERT INTO plan_versions (user_id, plan, patch, rationale, source, approved)
            VALUES (:u, CAST(:p AS jsonb), NULL,
                    'Initial cut plan: 1850 kcal / 135g protein', 'seed', true)
        """), {"u": user_id, "p": json.dumps(PLAN_V1)})
        db.commit()
    finally:
        db.close()

    print(f"user '{args.name}' created (id {user_id}) with plan v1 seeded")
    print(f"API token (save it now — used by the tracker pairing screen and the")
    print(f"iPhone Shortcut's X-Api-Token header):\n\n  {token}\n")

if __name__ == "__main__":
    main()
