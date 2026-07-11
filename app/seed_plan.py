"""The default plan v1 document + a re-seed CLI for an existing user.
Normally you don't run this — `python -m app.create_user` seeds automatically.
    python -m app.seed_plan --user 1   # re-seed if a user's plans were wiped
"""
import argparse
import json
from sqlalchemy import text
from app.db import SessionLocal

PLAN_V1 = {
    "targets": {"kcal": 1850, "protein_g": 135, "kcal_floor": 1600,
                "protein_min": 120, "protein_max": 150},
    "weekly_workouts": {"mon": "push", "tue": "legs", "wed": "core",
                        "thu": "pull", "fri": "push", "sat": "legs", "sun": "rest"},
    "meals": {
        "mon": {"theme": "Desi Default", "items": [
            {"id": "b", "name": "3-egg masala omelette + 2 phulkas", "kcal": 420, "protein_g": 26},
            {"id": "l", "name": "Dal + chicken sabzi (150g) + 2 rotis + salad", "kcal": 560, "protein_g": 42},
            {"id": "s", "name": "Whey shake + roasted chana (30g)", "kcal": 240, "protein_g": 31},
            {"id": "d", "name": "Paneer bhurji + 2 phulkas + kachumber", "kcal": 520, "protein_g": 25},
            {"id": "x", "name": "Dark chocolate (2 squares)", "kcal": 110, "protein_g": 1}]},
        "tue": {"theme": "Tandoori Tuesday", "items": [
            {"id": "b", "name": "Masala oats in milk + 1 boiled egg", "kcal": 420, "protein_g": 20},
            {"id": "l", "name": "Dal + 2 rotis + egg bhurji (2 eggs)", "kcal": 540, "protein_g": 28},
            {"id": "s", "name": "Whey shake", "kcal": 130, "protein_g": 25},
            {"id": "d", "name": "Tandoori chicken (200g) + jeera rice + salad", "kcal": 600, "protein_g": 48},
            {"id": "x", "name": "Watermelon / papaya bowl", "kcal": 60, "protein_g": 1}]},
        "wed": {"theme": "Chinese Wednesday", "items": [
            {"id": "b", "name": "3-egg omelette + 2 toast", "kcal": 420, "protein_g": 25},
            {"id": "l", "name": "Rajma/chole + rice (1.5 katori) + salad", "kcal": 560, "protein_g": 20},
            {"id": "s", "name": "Whey shake + 1 apple", "kcal": 210, "protein_g": 26},
            {"id": "d", "name": "Chilli chicken (200g) + veg fried rice", "kcal": 650, "protein_g": 52}]},
        "thu": {"theme": "Paneer Party", "items": [
            {"id": "b", "name": "Besan chilla stuffed with paneer + chutney", "kcal": 430, "protein_g": 24},
            {"id": "l", "name": "Dal + 2 rotis + veg sabzi + boiled egg", "kcal": 540, "protein_g": 24},
            {"id": "s", "name": "Whey shake + roasted makhana (20g)", "kcal": 220, "protein_g": 27},
            {"id": "d", "name": "Paneer tikka masala + 2 phulkas", "kcal": 560, "protein_g": 28},
            {"id": "x", "name": "Dark chocolate (2 squares)", "kcal": 110, "protein_g": 1}]},
        "fri": {"theme": "Naan Night", "items": [
            {"id": "b", "name": "Masala oats + 2 boiled eggs", "kcal": 430, "protein_g": 24},
            {"id": "l", "name": "Dal–roti–sabzi + salad", "kcal": 520, "protein_g": 20},
            {"id": "s", "name": "Whey shake", "kcal": 130, "protein_g": 25},
            {"id": "d", "name": "Tandoori naan + chicken tikka (200g) + chutney", "kcal": 700, "protein_g": 50}]},
        "sat": {"theme": "Street-Style Saturday", "items": [
            {"id": "b", "name": "Anda bhurji pav (3 eggs, 2 pav)", "kcal": 480, "protein_g": 26},
            {"id": "l", "name": "Soya chunk curry (50g dry) + rice", "kcal": 520, "protein_g": 32},
            {"id": "s", "name": "Whey shake + cucumber sticks", "kcal": 150, "protein_g": 26},
            {"id": "d", "name": "Chicken curry (150g) + 2 rotis", "kcal": 560, "protein_g": 40},
            {"id": "x", "name": "Frozen banana nice-cream + peanut butter", "kcal": 150, "protein_g": 3}]},
        "sun": {"theme": "Biryani Sunday", "items": [
            {"id": "b", "name": "2 moong dal chillas + curd dip", "kcal": 380, "protein_g": 20},
            {"id": "l", "name": "Homemade chicken biryani + raita + salad", "kcal": 750, "protein_g": 48},
            {"id": "s", "name": "Whey shake", "kcal": 130, "protein_g": 25},
            {"id": "d", "name": "Light dal/soup + 1 roti + 2 boiled eggs", "kcal": 420, "protein_g": 24},
            {"id": "x", "name": "Dark chocolate (2 squares)", "kcal": 110, "protein_g": 1}]},
    },
}

def main():
    p = argparse.ArgumentParser(description="Re-seed plan v1 for an existing user")
    p.add_argument("--user", type=int, required=True, help="users.id to seed for")
    args = p.parse_args()
    db = SessionLocal()
    try:
        exists = db.execute(text(
            "SELECT 1 FROM plan_versions WHERE user_id=:u LIMIT 1"), {"u": args.user}).first()
        if exists:
            print(f"user {args.user} already has plan versions — skipping")
            return
        db.execute(text("""
            INSERT INTO plan_versions (user_id, plan, patch, rationale, source, approved)
            VALUES (:u, CAST(:p AS jsonb), NULL,
                    'Initial cut plan: 1850 kcal / 135g protein', 'seed', true)
        """), {"u": args.user, "p": json.dumps(PLAN_V1)})
        db.commit()
        print(f"seeded plan v1 for user {args.user}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
