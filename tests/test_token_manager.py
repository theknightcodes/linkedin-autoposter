"""Tests for token_manager — mocks LinkedIn token endpoint."""
import os
import time
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def env_setup(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LINKEDIN_ACCESS_TOKEN=old_token\n"
        "LINKEDIN_REFRESH_TOKEN=refresh_tok\n"
        f"LINKEDIN_TOKEN_EXPIRES_AT={int(time.time()) + 9999}\n"
        f"LINKEDIN_REFRESH_ISSUED_AT={int(time.time())}\n"
    )
    monkeypatch.setattr("src.token_manager.ENV_PATH", env_file)
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "old_token")
    monkeypatch.setenv("LINKEDIN_REFRESH_TOKEN", "refresh_tok")
    monkeypatch.setenv("LINKEDIN_TOKEN_EXPIRES_AT", str(int(time.time()) + 9999))
    monkeypatch.setenv("LINKEDIN_REFRESH_ISSUED_AT", str(int(time.time())))
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test_id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "test_secret")


def test_valid_token_returns_without_refresh():
    import src.token_manager as tm
    token = tm.get_valid_token()
    assert token == "old_token"


def test_token_refreshed_when_expiring(monkeypatch):
    import src.token_manager as tm
    # Set expiry to 1 hour from now (within the 24h buffer)
    monkeypatch.setenv("LINKEDIN_TOKEN_EXPIRES_AT", str(int(time.time()) + 3600))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "new_token",
        "refresh_token": "new_refresh",
        "expires_in": 5183944,
    }

    with patch("src.token_manager.requests.post", return_value=mock_resp):
        token = tm.get_valid_token()

    assert token == "new_token"
    assert os.environ.get("LINKEDIN_ACCESS_TOKEN") == "new_token"


def test_refresh_failure_raises(monkeypatch):
    import src.token_manager as tm
    monkeypatch.setenv("LINKEDIN_TOKEN_EXPIRES_AT", str(int(time.time()) + 100))

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "invalid_grant"

    with patch("src.token_manager.requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Token refresh failed"):
            tm.get_valid_token()


def test_env_updated_after_refresh(monkeypatch, tmp_path):
    import src.token_manager as tm
    monkeypatch.setenv("LINKEDIN_TOKEN_EXPIRES_AT", str(int(time.time()) + 100))

    env_file = tmp_path / ".env2"
    env_file.write_text("LINKEDIN_ACCESS_TOKEN=old\n")
    monkeypatch.setattr("src.token_manager.ENV_PATH", env_file)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "fresh_token",
        "expires_in": 5183944,
    }

    with patch("src.token_manager.requests.post", return_value=mock_resp):
        tm.refresh_access_token("old_refresh")

    content = env_file.read_text()
    assert "fresh_token" in content


def test_no_access_token_raises(monkeypatch):
    import src.token_manager as tm
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "")
    with pytest.raises(RuntimeError, match="oauth_setup"):
        tm.get_valid_token()
