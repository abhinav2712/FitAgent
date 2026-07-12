from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

def get_current_user(x_api_token: str = Header(default=""),
                     db: Session = Depends(get_db)) -> dict:
    """Resolve X-Api-Token → user row. One credential per user, used by both
    the tracker app and that user's iPhone Shortcut. Tokens are minted by
    `python -m app.create_user`. (HMAC signing is still the v2 upgrade.)"""
    row = db.execute(text(
        "SELECT id, name, telegram_chat_id, profile, tz, lat, lng FROM users WHERE api_token = :t"),
        {"t": x_api_token}).mappings().first()
    if not row:
        raise HTTPException(status_code=401, detail="invalid or missing X-Api-Token")
    return dict(row)
