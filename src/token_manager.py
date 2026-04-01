"""LinkedIn OAuth token storage, refresh, and expiry monitoring."""
import logging
import os
import time
from pathlib import Path

import requests

from src.config import (
    ENV_PATH,
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

TOKEN_URL          = "https://www.linkedin.com/oauth/v2/accessToken"
TOKEN_EXPIRY_BUFFER = 24 * 3600          # refresh if < 24h remaining
REFRESH_WARNING_DAYS = 30               # warn this many days before refresh token expires
REFRESH_TOKEN_TTL    = 365 * 24 * 3600  # LinkedIn refresh tokens live ~365 days


def _read_env() -> dict[str, str]:
    """Read current .env as key-value pairs (preserves order and comments)."""
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _write_env(updates: dict[str, str]) -> None:
    """Atomically update specific keys in .env, preserving all other lines."""
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        if line.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in updates:
            new_lines.append(f"{k}={updates[k]}")
            updated_keys.add(k)
        else:
            new_lines.append(line)

    # Append any keys not yet in the file
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}")

    tmp = ENV_PATH.with_suffix(".env.tmp")
    tmp.write_text("\n".join(new_lines) + "\n")
    tmp.replace(ENV_PATH)

    # Reload into os.environ
    for k, v in updates.items():
        os.environ[k] = v


def get_valid_token() -> str:
    """
    Return a valid access token, refreshing it automatically if needed.
    Raises RuntimeError if refresh fails (caller should abort the run).
    """
    access_token  = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    expires_at    = float(os.environ.get("LINKEDIN_TOKEN_EXPIRES_AT", "0"))
    refresh_token = os.environ.get("LINKEDIN_REFRESH_TOKEN", "")

    if not access_token:
        raise RuntimeError(
            "No LINKEDIN_ACCESS_TOKEN found. Run: python -m src.oauth_setup"
        )

    # Check if approaching expiry
    now = time.time()
    if expires_at - now < TOKEN_EXPIRY_BUFFER:
        logger.info("Access token expiring soon — refreshing…")
        if not refresh_token:
            raise RuntimeError(
                "Access token expired and no LINKEDIN_REFRESH_TOKEN available. "
                "Re-run: python -m src.oauth_setup"
            )
        access_token = refresh_access_token(refresh_token)

    # Warn if refresh token is aging
    refresh_issued_at = float(os.environ.get("LINKEDIN_REFRESH_ISSUED_AT", "0"))
    if refresh_issued_at:
        days_left = (refresh_issued_at + REFRESH_TOKEN_TTL - now) / 86400
        if days_left < REFRESH_WARNING_DAYS:
            logger.warning(
                "⚠️  LinkedIn refresh token expires in %.0f days! "
                "Re-run oauth_setup.py before it does.",
                days_left,
            )

    return access_token


def refresh_access_token(refresh_token: str) -> str:
    """
    Use the refresh token to obtain a new access token.
    Updates .env in-place and returns the new access token.
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Token refresh failed [{resp.status_code}]: {resp.text}"
        )

    data = resp.json()
    new_access   = data["access_token"]
    expires_in   = data.get("expires_in", 5183944)  # ~60 days default
    new_refresh  = data.get("refresh_token", refresh_token)
    now          = time.time()

    _write_env({
        "LINKEDIN_ACCESS_TOKEN":    new_access,
        "LINKEDIN_REFRESH_TOKEN":   new_refresh,
        "LINKEDIN_TOKEN_EXPIRES_AT": str(int(now + expires_in)),
        "LINKEDIN_REFRESH_ISSUED_AT": str(int(now)),
    })

    logger.info("Access token refreshed. Expires in %.0f days.", expires_in / 86400)
    return new_access
