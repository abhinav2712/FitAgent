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
    """Browser geolocation or a manual pin, never a hard-coded default.
    Display + future use only: live Swiggy search (Food and Instamart) turned
    out to be anchored to the account's saved delivery address, not lat/lng —
    see agent/swiggy_mcp._resolve_address_id."""
    db.execute(text("""
        UPDATE users SET lat = :lat, lng = :lng, location_label = :label WHERE id = :u
    """), {"lat": loc.lat, "lng": loc.lng, "label": loc.label, "u": user["id"]})
    db.commit()
    return {"ok": True}
