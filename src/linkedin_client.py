"""LinkedIn API v2 client for creating UGC posts with optional image attachments."""
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from src.token_manager import get_valid_token

logger = logging.getLogger(__name__)

POST_URL       = "https://api.linkedin.com/rest/posts"
IMAGES_URL     = "https://api.linkedin.com/rest/images"
HEADERS_BASE   = {
    "Content-Type":      "application/json",
    "LinkedIn-Version":  "202601",
}

MAX_RETRIES     = 3
RETRY_BACKOFF   = [2, 5, 10]   # seconds between retries


def upload_image(image_path: Path, person_urn: str) -> str:
    """
    Upload a local image to LinkedIn and return the image URN.

    Uses the LinkedIn Images API:
      1. POST /rest/images?action=initializeUpload  → get uploadUrl + image URN
      2. PUT <uploadUrl> with binary image data
      3. Return the image URN for use in create_post_with_image()

    Raises RuntimeError on failure.
    """
    token = get_valid_token()
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}

    # Step 1: Initialize upload
    init_payload = {
        "initializeUploadRequest": {
            "owner": person_urn,
        }
    }
    init_resp = requests.post(
        f"{IMAGES_URL}?action=initializeUpload",
        json=init_payload,
        headers=headers,
        timeout=20,
    )
    if init_resp.status_code != 200:
        raise RuntimeError(
            f"Image upload init failed [{init_resp.status_code}]: {init_resp.text}"
        )

    upload_data = init_resp.json().get("value", {})
    upload_url  = upload_data.get("uploadUrl")
    image_urn   = upload_data.get("image")

    if not upload_url or not image_urn:
        raise RuntimeError(f"Unexpected initializeUpload response: {init_resp.text}")

    logger.debug("Image upload URL obtained. URN: %s", image_urn)

    # Step 2: Upload binary
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    put_resp = requests.put(
        upload_url,
        data=image_bytes,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"},
        timeout=60,
    )
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Image binary upload failed [{put_resp.status_code}]: {put_resp.text}"
        )

    logger.info("Image uploaded. URN: %s", image_urn)
    return image_urn


def create_post(text: str, person_urn: str, image_urn: Optional[str] = None) -> str:
    """
    Post `text` to LinkedIn as the user identified by `person_urn`.
    If `image_urn` is provided, attaches the image to the post.
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

    if image_urn:
        payload["content"] = {
            "media": {
                "id": image_urn,
            }
        }
        logger.debug("Post will include image URN: %s", image_urn)

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
