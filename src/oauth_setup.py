"""
One-time interactive OAuth 2.0 setup for LinkedIn.

Run once:
    conda activate linkedin-autoposter
    python -m src.oauth_setup

This will:
  1. Open your browser to the LinkedIn authorization page
  2. Capture the callback on localhost:8080
  3. Exchange the auth code for access + refresh tokens
  4. Fetch your LinkedIn person URN
  5. Write everything to .env
"""
import os
import secrets
import sys
import time
import webbrowser
from threading import Timer
from urllib.parse import urlencode, urlparse, parse_qs

from flask import Flask, request, redirect

from src.config import (
    ENV_PATH,
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
)
from src.token_manager import _write_env

import requests

SCOPES       = "w_member_social"
AUTH_URL     = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL    = "https://www.linkedin.com/oauth/v2/accessToken"
PROFILE_URL  = "https://api.linkedin.com/v2/me"
STATE        = secrets.token_urlsafe(32)  # Random per-run — prevents CSRF

app = Flask(__name__)
_result: dict = {}


@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        _result["error"] = request.args.get("error_description", error)
        _shutdown()
        return f"<h2>Error: {_result['error']}</h2><p>Check terminal.</p>", 400

    code  = request.args.get("code")
    state = request.args.get("state")

    if state != STATE:
        _result["error"] = "State mismatch — possible CSRF."
        _shutdown()
        return "<h2>State mismatch error</h2>", 400

    # Exchange code for tokens
    resp = requests.post(TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  LINKEDIN_REDIRECT_URI,
        "client_id":     LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }, timeout=15)

    if resp.status_code != 200:
        _result["error"] = f"Token exchange failed: {resp.text}"
        _shutdown()
        return "<h2>Token exchange failed</h2><pre>" + resp.text + "</pre>", 400

    data = resp.json()
    _result["access_token"]   = data["access_token"]
    _result["refresh_token"]  = data.get("refresh_token", "")
    _result["expires_in"]     = data.get("expires_in", 5183944)

    # Fetch person URN via OpenID userinfo (works with openid+profile scope)
    profile_resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {data['access_token']}"},
        timeout=10,
    )
    if profile_resp.status_code != 200:
        # Fallback to v2/me
        profile_resp = requests.get(
            PROFILE_URL,
            headers={
                "Authorization": f"Bearer {data['access_token']}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=10,
        )
    profile = profile_resp.json() if profile_resp.status_code == 200 else {}
    # userinfo returns "sub" as the person ID (alphanumeric), v2/me returns "id" (numeric)
    _result["person_urn"] = profile.get("sub", "") or profile.get("id", "")
    first = profile.get("given_name", "") or profile.get("localizedFirstName", "")
    last  = profile.get("family_name", "") or profile.get("localizedLastName", "")
    _result["name"] = f"{first} {last}".strip() or "Unknown"

    # Write tokens now — before shutdown kills the process
    now = int(time.time())
    updates = {
        "LINKEDIN_ACCESS_TOKEN":      _result["access_token"],
        "LINKEDIN_REFRESH_TOKEN":     _result.get("refresh_token", ""),
        "LINKEDIN_TOKEN_EXPIRES_AT":  str(now + _result["expires_in"]),
        "LINKEDIN_REFRESH_ISSUED_AT": str(now),
    }
    # Only update URN if we got one — preserve existing value otherwise
    if _result.get("person_urn"):
        updates["LINKEDIN_PERSON_URN"] = f"urn:li:person:{_result['person_urn']}"
    _write_env(updates)

    urn_note = (
        f"<p>Person URN: <code>urn:li:person:{_result['person_urn']}</code></p>"
        if _result["person_urn"]
        else "<p><strong>⚠️ Person URN not found</strong> — set LINKEDIN_PERSON_URN manually in .env (see terminal).</p>"
    )

    _shutdown()
    return (
        "<h2>✅ Authorization successful!</h2>"
        f"<p>Welcome, <strong>{_result['name']}</strong>!</p>"
        + urn_note +
        "<p>You can close this tab. Your tokens have been saved to <code>.env</code>.</p>"
    )


def _shutdown():
    Timer(1.0, lambda: os.kill(os.getpid(), 9)).start()


def main():
    if not LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_ID == "YOUR_CLIENT_ID":
        print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
        sys.exit(1)

    params = urlencode({
        "response_type": "code",
        "client_id":     LINKEDIN_CLIENT_ID,
        "redirect_uri":  LINKEDIN_REDIRECT_URI,
        "state":         STATE,
        "scope":         SCOPES,
    })
    auth_url = f"{AUTH_URL}?{params}"

    print("\n─" * 40)
    print("LinkedIn OAuth Setup")
    print("─" * 40)
    print(f"Opening browser to:\n{auth_url}\n")
    print("Waiting for callback on http://localhost:8080/callback …\n")
    webbrowser.open(auth_url)

    # Flask blocks until _shutdown() kills process (after callback)
    try:
        app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)
    except SystemExit:
        pass

    if "error" in _result:
        print(f"\nERROR: {_result['error']}")
        sys.exit(1)

    # Tokens were already written inside the callback (before SIGKILL)
    print("\n✅ Tokens saved to .env")
    print(f"   Name:       {_result.get('name', 'Unknown')}")
    if _result.get("person_urn"):
        print(f"   Person URN: urn:li:member:{_result['person_urn']}")
    else:
        print("   ⚠️  Person URN not captured (w_member_social scope doesn't expose profile).")
        print("   Find your URN: go to your LinkedIn profile → copy the ID from the URL")
        print("   e.g. linkedin.com/in/john-doe-123abc → set LINKEDIN_PERSON_URN=urn:li:person:123abc in .env")
    print(f"   Expires in: {_result.get('expires_in', 0) // 86400} days")
    print("\nRun a test post: python -m src.main --dry-run")


if __name__ == "__main__":
    main()
