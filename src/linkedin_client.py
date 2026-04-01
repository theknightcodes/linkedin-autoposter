"""LinkedIn API v2 client for creating UGC posts."""
import logging
import time

import requests

from src.token_manager import get_valid_token

logger = logging.getLogger(__name__)

POST_URL     = "https://api.linkedin.com/rest/posts"
HEADERS_BASE = {
    "Content-Type":      "application/json",
    "LinkedIn-Version":  "202601",
}

MAX_RETRIES     = 3
RETRY_BACKOFF   = [2, 5, 10]   # seconds between retries


def create_post(text: str, person_urn: str) -> str:
    """
    Post `text` to LinkedIn as the user identified by `person_urn`.
    Returns the LinkedIn post URN on success.
    Raises RuntimeError on persistent failure.
    """
    import os
    person_urn = person_urn or os.environ.get("LINKEDIN_PERSON_URN", "")
    if not person_urn:
        raise RuntimeError(
            "LINKEDIN_PERSON_URN not set. Re-run: python -m src.oauth_setup"
        )

    payload = {
        "author":         person_urn,
        "commentary":     text,
        "visibility":     "PUBLIC",
        "distribution": {
            "feedDistribution":              "MAIN_FEED",
            "targetEntities":                [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState":             "PUBLISHED",
        "isReshareDisabledByAuthor":  False,
    }

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            token = get_valid_token()
            headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}

            resp = requests.post(POST_URL, json=payload, headers=headers, timeout=20)

            if resp.status_code == 201:
                urn = resp.headers.get("x-restli-id") or (resp.json().get("id", "unknown") if resp.text else "unknown")
                logger.info("Posted successfully. URN: %s", urn)
                return urn

            if resp.status_code == 401:
                logger.warning("401 Unauthorized — token may have just expired. Retrying after refresh.")
                import os; os.environ["LINKEDIN_TOKEN_EXPIRES_AT"] = "0"   # force refresh next get_valid_token
                last_error = RuntimeError(f"401: {resp.text}")

            elif resp.status_code == 422:
                raise RuntimeError(f"422 Unprocessable: {resp.text}")     # don't retry invalid payload

            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning("Rate limited. Waiting %ds.", retry_after)
                time.sleep(retry_after)
                last_error = RuntimeError(f"429 rate limited")

            else:
                logger.error("LinkedIn API error [%d]: %s", resp.status_code, resp.text)
                last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

        except requests.RequestException as exc:
            logger.warning("Network error on attempt %d: %s", attempt + 1, exc)
            last_error = exc

        if attempt < MAX_RETRIES - 1:
            wait = RETRY_BACKOFF[attempt]
            logger.info("Retrying in %ds… (%d/%d)", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)

    raise RuntimeError(
        f"LinkedIn post failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )
