import pytest
from agent.guardrails import apply_and_validate, requires_human_approval, GuardrailViolation

PLAN = {
    "targets": {"kcal": 1850, "protein_g": 135},
    "weekly_workouts": {"mon": "push"},
    "meals": {"mon": {"theme": "t", "items": [
        {"id": "b", "name": "eggs", "kcal": 900, "protein_g": 70},
        {"id": "d", "name": "chicken", "kcal": 900, "protein_g": 65},
    ]}},
}

def test_valid_small_swap_passes():
    patch = [{"op": "replace", "path": "/meals/mon/items/0/kcal", "value": 850}]
    new = apply_and_validate(PLAN, patch)
    assert new["meals"]["mon"]["items"][0]["kcal"] == 850

def test_starvation_patch_rejected():
    patch = [{"op": "replace", "path": "/targets/kcal", "value": 1200}]
    with pytest.raises(GuardrailViolation):
        apply_and_validate(PLAN, patch)

def test_protein_floor_enforced():
    patch = [{"op": "replace", "path": "/meals/mon/items/0/protein_g", "value": 10}]
    with pytest.raises(GuardrailViolation):
        apply_and_validate(PLAN, patch)

def test_structural_changes_need_human():
    assert requires_human_approval([{"op": "replace", "path": "/targets/kcal", "value": 1800}])
    assert not requires_human_approval([{"op": "replace", "path": "/meals/mon/items/0/kcal", "value": 850}])

def test_seed_plan_passes_its_own_guardrails():
    """apply_and_validate revalidates EVERY day, so a seed plan that violates a
    floor makes all future patches unappliable. Empty patch = pure validation.
    (Regression: thu/fri/sun protein once summed 104/119/118g — below the 120 floor.)"""
    from app.seed_plan import PLAN_V1
    apply_and_validate(PLAN_V1, [])
