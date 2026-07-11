"""THE core safety principle: the LLM proposes, this module disposes.
All plan patches pass through validate_plan() BEFORE persisting.
These bounds are hard-coded on purpose — the agent cannot talk its way past them.
"""
import jsonpatch

KCAL_FLOOR = 1600          # never plan below this
PROTEIN_MIN, PROTEIN_MAX = 120, 150
MAX_DAY_KCAL_CHANGE_PCT = 15   # single agent patch can't swing a day >15%

class GuardrailViolation(Exception):
    pass

def day_totals(day_items):
    return (sum(i["kcal"] for i in day_items),
            sum(i["protein_g"] for i in day_items))

def apply_and_validate(current_plan: dict, patch_ops: list) -> dict:
    """Apply RFC6902 patch, then enforce invariants. Raises GuardrailViolation."""
    new_plan = jsonpatch.apply_patch(current_plan, patch_ops)

    t = new_plan.get("targets", {})
    if t.get("kcal", 0) < KCAL_FLOOR:
        raise GuardrailViolation(f"target kcal {t.get('kcal')} below floor {KCAL_FLOOR}")
    if not (PROTEIN_MIN <= t.get("protein_g", 0) <= PROTEIN_MAX):
        raise GuardrailViolation(f"protein target {t.get('protein_g')} outside {PROTEIN_MIN}-{PROTEIN_MAX}g")

    for day, block in new_plan.get("meals", {}).items():
        kcal, protein = day_totals(block["items"])
        if kcal < KCAL_FLOOR:
            raise GuardrailViolation(f"{day} totals {kcal} kcal — below floor {KCAL_FLOOR}")
        if protein < PROTEIN_MIN:
            raise GuardrailViolation(f"{day} protein {protein}g — below minimum {PROTEIN_MIN}g")
        old = current_plan.get("meals", {}).get(day)
        if old:
            old_kcal, _ = day_totals(old["items"])
            if old_kcal and abs(kcal - old_kcal) / old_kcal * 100 > MAX_DAY_KCAL_CHANGE_PCT:
                raise GuardrailViolation(
                    f"{day} kcal change {old_kcal}->{kcal} exceeds {MAX_DAY_KCAL_CHANGE_PCT}%")
    return new_plan

def requires_human_approval(patch_ops: list) -> bool:
    """Structural changes go to Telegram approve/reject; small swaps auto-apply."""
    structural_paths = ("/targets", "/weekly_workouts")
    for op in patch_ops:
        if op.get("path", "").startswith(structural_paths):
            return True
    return len(patch_ops) > 4   # big multi-edit patches also need a human
