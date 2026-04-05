"""Tests for linkedin_client — image upload and post-with-image flow."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


PERSON_URN = "urn:li:person:abc123"
IMAGE_URN  = "urn:li:image:xyz789"
POST_TEXT  = "Test post content #AI #Claude #LLM #Data"


def _mock_token():
    return "fake_access_token"


# ── upload_image ──────────────────────────────────────────────────

def test_upload_image_success():
    """Full happy path: initializeUpload + binary PUT → returns image URN."""
    from src.linkedin_client import upload_image

    init_response = MagicMock()
    init_response.status_code = 200
    init_response.json.return_value = {
        "value": {
            "uploadUrl": "https://storage.linkedin.com/upload/abc",
            "image": IMAGE_URN,
        }
    }

    put_response = MagicMock()
    put_response.status_code = 201

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG fake image data")
        tmp_path = Path(f.name)

    with patch("src.linkedin_client.get_valid_token", return_value="fake_token"):
        with patch("requests.post", return_value=init_response):
            with patch("requests.put", return_value=put_response):
                result = upload_image(tmp_path, PERSON_URN)

    assert result == IMAGE_URN


def test_upload_image_init_failure_raises():
    """If initializeUpload returns non-200, raises RuntimeError."""
    from src.linkedin_client import upload_image

    init_response = MagicMock()
    init_response.status_code = 403
    init_response.text = "Forbidden"

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG")
        tmp_path = Path(f.name)

    with patch("src.linkedin_client.get_valid_token", return_value="fake_token"):
        with patch("requests.post", return_value=init_response):
            with pytest.raises(RuntimeError, match="upload init failed"):
                upload_image(tmp_path, PERSON_URN)


def test_upload_image_put_failure_raises():
    """If binary PUT returns non-200/201, raises RuntimeError."""
    from src.linkedin_client import upload_image

    init_response = MagicMock()
    init_response.status_code = 200
    init_response.json.return_value = {
        "value": {
            "uploadUrl": "https://storage.linkedin.com/upload/abc",
            "image": IMAGE_URN,
        }
    }

    put_response = MagicMock()
    put_response.status_code = 500
    put_response.text = "Internal Server Error"

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG")
        tmp_path = Path(f.name)

    with patch("src.linkedin_client.get_valid_token", return_value="fake_token"):
        with patch("requests.post", return_value=init_response):
            with patch("requests.put", return_value=put_response):
                with pytest.raises(RuntimeError, match="binary upload failed"):
                    upload_image(tmp_path, PERSON_URN)


# ── create_post (with image_urn) ──────────────────────────────────

def test_create_post_with_image_urn_in_payload():
    """When image_urn is provided, payload includes content.media."""
    from src.linkedin_client import create_post

    post_response = MagicMock()
    post_response.status_code = 201
    post_response.headers = {"x-restli-id": "urn:li:ugcPost:12345"}
    post_response.text = ""

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["payload"] = json
        return post_response

    with patch("src.linkedin_client.get_valid_token", return_value="fake_token"):
        with patch("requests.post", side_effect=fake_post):
            result = create_post(POST_TEXT, PERSON_URN, image_urn=IMAGE_URN)

    assert result == "urn:li:ugcPost:12345"
    assert "content" in captured["payload"]
    assert captured["payload"]["content"]["media"]["id"] == IMAGE_URN


def test_create_post_without_image_urn_no_content_key():
    """When image_urn is None, payload does NOT include content.media."""
    from src.linkedin_client import create_post

    post_response = MagicMock()
    post_response.status_code = 201
    post_response.headers = {"x-restli-id": "urn:li:ugcPost:99999"}
    post_response.text = ""

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["payload"] = json
        return post_response

    with patch("src.linkedin_client.get_valid_token", return_value="fake_token"):
        with patch("requests.post", side_effect=fake_post):
            result = create_post(POST_TEXT, PERSON_URN, image_urn=None)

    assert "content" not in captured["payload"]
    assert result == "urn:li:ugcPost:99999"
