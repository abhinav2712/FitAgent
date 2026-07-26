from pydantic import BaseModel, Field
from datetime import date as Date

class WorkoutIn(BaseModel):
    type: str
    distance_km: float | None = None
    duration_min: float | None = None
    avg_pace_min_per_km: float | None = None

class HealthPayload(BaseModel):
    # All optional and defaulting to None (NOT 0) so a payload can carry just
    # one metric — e.g. a steps-only Shortcut and a calories-only Shortcut each
    # update their own field without the second clobbering the first. The
    # webhook COALESCEs: a missing field leaves the stored value untouched.
    date: Date
    steps: int | None = None
    active_kcal: int | None = None
    workouts: list[WorkoutIn] | None = None

class MealLogIn(BaseModel):
    date: Date
    meal_id: str
    name: str
    kcal: int
    protein_g: int
    checked: bool = True

class WeightIn(BaseModel):
    date: Date
    weight_kg: float

class CommentIn(BaseModel):
    date: Date
    text: str

class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    label: str | None = None   # freeform display text, e.g. "HSR Layout, Bengaluru"
