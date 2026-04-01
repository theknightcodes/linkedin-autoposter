"""Tests for content_generator — mocks the Anthropic API."""
import importlib
from unittest.mock import MagicMock, patch

import pytest


def _make_response(text: str):
    """Build a mock anthropic messages response."""
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


@pytest.fixture()
def generator():
    import src.content_generator as gen
    importlib.reload(gen)
    return gen


GOOD_POST = (
    "Most engineers don't realize Claude's context window resets between API calls — "
    "that 'memory' is entirely your responsibility to manage.\n\n"
    "When you hit the limit, naive truncation breaks reasoning chains mid-thought. "
    "The fix: always truncate from the middle of the conversation, not the end. "
    "Keep the system prompt and the last 3 turns intact.\n\n"
    "Concrete tip: if you're using the Anthropic SDK, store turns as a list and slice "
    "from index 1 (not 0) when over 80% of your token budget.\n\n"
    "#AI #Claude #LLM #PromptEngineering #AIEngineering"
)

TOO_SHORT = "Short post. #AI"
TOO_LONG  = "x" * 1400


def test_valid_post_passes(generator):
    with patch.object(generator._get_client(), "messages") as mock_messages:
        mock_messages.create.return_value = _make_response(GOOD_POST)
        result = generator.generate_post("ai_tips", [])
    assert result == GOOD_POST


def test_too_short_raises(generator):
    with pytest.raises(ValueError, match="too short"):
        generator._validate(TOO_SHORT, "ai_tips")


def test_too_long_raises(generator):
    with pytest.raises(ValueError, match="too long"):
        generator._validate(TOO_LONG, "ai_tips")


def test_missing_hashtags_raises(generator):
    no_tags = "A" * 500  # valid length, no hashtags
    with pytest.raises(ValueError, match="hashtag"):
        generator._validate(no_tags, "ai_tips")


def test_hashtag_count_ok(generator):
    post = "A" * 500 + " #AI #Claude #LLM"
    generator._validate(post, "ai_tips")   # should not raise


def test_generate_uses_recent_posts(generator):
    """Verify recent post context is passed to the model."""
    recent = ["Previous post about dbt", "Previous post about Airflow"]
    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _make_response(GOOD_POST)

    with patch("anthropic.Anthropic") as MockCls:
        instance = MockCls.return_value
        instance.messages.create.side_effect = fake_create
        generator._client = instance
        generator.generate_post("ai_tips", recent)

    user_msg = captured["messages"][0]["content"]
    assert "Previous post about dbt" in user_msg
