from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import LocationIn
from app.security import get_current_user

router = APIRouter()

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Just enough to render the location picker — never the token or Swiggy auth."""
    return {"name": user["name"], "lat": user["lat"], "lng": user["lng"],
            "location_label": user.get("location_label")}

@router.put("/me/location")
def set_location(loc: LocationIn, db: Session = Depends(get_db),
                 user: dict = Depends(get_current_user)):
    """Sets where Swiggy searches near — browser geolocation or a manual pin,
    never a hard-coded default. Used by Food's lat/lng search and shown to the
    user; Instamart resolves its own saved delivery address once linked."""
    db.execute(text("""
        UPDATE users SET lat = :lat, lng = :lng, location_label = :label WHERE id = :u
    """), {"lat": loc.lat, "lng": loc.lng, "label": loc.label, "u": user["id"]})
    db.commit()
    return {"ok": True}
