"""Link a FitAgent user to their Swiggy account (OAuth 2.1 + PKCE, one-time
phone + OTP in the browser). Stores the 5-day Bearer token on the users row:
    python -m app.swiggy_auth <user_id>
Re-run whenever the token expires (Swiggy v1.0 has no refresh tokens).
Only read-only search tools are ever called with it — see agent/swiggy_mcp.py.
"""
import argparse
import base64
import hashlib
import http.server
import secrets
import time
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from sqlalchemy import text
from app.db import SessionLocal

AUTH_BASE = "https://mcp.swiggy.com"
REDIRECT_URI = "http://localhost:8765/callback"

def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge

def _register_client() -> str:
    """Dynamic Client Registration (RFC 7591) — client identity is automatic."""
    r = httpx.post(f"{AUTH_BASE}/auth/register", json={
        "client_name": "FitAgent (personal, read-only search)",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, timeout=15)
    r.raise_for_status()
    return r.json()["client_id"]

def _wait_for_code(state: str) -> str:
    """Tiny one-shot HTTP server for the OAuth callback."""
    box = {}
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] != state:
                self.send_response(400); self.end_headers(); return
            box["code"] = q.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"FitAgent: Swiggy linked. You can close this tab.")
        def log_message(self, *a):  # keep the CLI output clean
            pass
    srv = http.server.HTTPServer(("localhost", 8765), Handler)
    srv.timeout = 30  # per-request wait; the deadline below bounds the whole flow
    deadline = time.time() + 600
    while "code" not in box and time.time() < deadline:
        srv.handle_request()  # blocks until a request or timeout — no busy spin
    srv.server_close()
    if "code" not in box:
        raise SystemExit("Timed out after 10 min waiting for the Swiggy login callback.")
    return box["code"]

def main():
    p = argparse.ArgumentParser(description="Link a user's Swiggy account")
    p.add_argument("user_id", type=int)
    args = p.parse_args()

    client_id = _register_client()
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    url = f"{AUTH_BASE}/auth/authorize?" + urlencode({
        "response_type": "code", "client_id": client_id,
        "redirect_uri": REDIRECT_URI, "code_challenge": challenge,
        "code_challenge_method": "S256", "state": state, "scope": "mcp:tools",
    })
    print("Opening browser for Swiggy phone + OTP login…\nIf it doesn't open:", url)
    webbrowser.open(url)
    code = _wait_for_code(state)

    r = httpx.post(f"{AUTH_BASE}/auth/token", json={
        "grant_type": "authorization_code", "code": code,
        "code_verifier": verifier, "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
    }, timeout=15)
    r.raise_for_status()
    tok = r.json()

    db = SessionLocal()
    try:
        db.execute(text("""
            UPDATE users SET swiggy_token = :t,
                   swiggy_token_expires_at = now() + make_interval(secs => :e)
            WHERE id = :u
        """), {"t": tok["access_token"], "e": int(tok.get("expires_in", 432000)),
               "u": args.user_id})
        db.commit()
    finally:
        db.close()
    print(f"Linked: user {args.user_id} — token valid ~{tok.get('expires_in', 432000)//86400} days. "
          f"Set SWIGGY_MOCK=false in .env and restart to go live.")

if __name__ == "__main__":
    main()
