"""Tests for image_generator — mocks Gemini API and Remotion subprocess."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ── Fixtures ─────────────────────────────────────────────────────

SAMPLE_POST = (
    "Most engineers don't realize Claude's context window resets between API calls — "
    "that 'memory' is entirely your responsibility to manage.\n\n"
    "When you hit the limit, naive truncation breaks reasoning chains mid-thought. "
    "The fix: always truncate from the middle of the conversation, not the end.\n\n"
    "#AI #Claude #LLM #PromptEngineering #AIEngineering"
)

GOOD_PROPS = {
    "headline": "Stop truncating your LLM context from the end",
    "insight": "Keep the system prompt and last 3 turns; cut from the middle.",
    "topic": "ai_tips",
}


# ── extract_image_props ───────────────────────────────────────────

def test_extract_image_props_gemini_success():
    """Gemini returns valid JSON → props dict with correct keys."""
    from src import image_generator

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "headline": GOOD_PROPS["headline"],
        "insight": GOOD_PROPS["insight"],
    })

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("os.environ.get", side_effect=lambda k, d="": "fake_key" if k == "GEMINI_API_KEY" else d):
        with patch("google.genai.Client", return_value=mock_client):
            result = image_generator.extract_image_props(SAMPLE_POST, "ai_tips")

    assert result["headline"] == GOOD_PROPS["headline"]
    assert result["insight"] == GOOD_PROPS["insight"]
    assert result["topic"] == "ai_tips"


def test_extract_image_props_strips_markdown_fences():
    """Gemini wraps JSON in ```json fences → should still parse correctly."""
    from src import image_generator

    fenced = "```json\n" + json.dumps({"headline": "Bold headline", "insight": "Key insight."}) + "\n```"
    mock_response = MagicMock()
    mock_response.text = fenced

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("os.environ.get", side_effect=lambda k, d="": "fake_key" if k == "GEMINI_API_KEY" else d):
        with patch("google.genai.Client", return_value=mock_client):
            result = image_generator.extract_image_props(SAMPLE_POST, "claude_features")

    assert result["headline"] == "Bold headline"
    assert result["topic"] == "claude_features"


def test_extract_image_props_fallback_on_gemini_error():
    """If Gemini raises, falls back to first-sentence truncation."""
    from src import image_generator

    with patch("os.environ.get", return_value=""):
        # GEMINI_API_KEY empty → RuntimeError → fallback
        result = image_generator.extract_image_props(SAMPLE_POST, "ai_tips")

    assert "headline" in result
    assert "topic" in result
    assert result["topic"] == "ai_tips"
    # Fallback headline should be a non-empty string
    assert len(result["headline"]) > 0


def test_fallback_props_truncates_long_sentence():
    """Fallback truncates first sentence to 80 chars."""
    from src.image_generator import _fallback_props

    long_post = "A" * 200 + ". Rest of post."
    props = _fallback_props(long_post, "lessons_learned")
    assert len(props["headline"]) <= 80
    assert props["topic"] == "lessons_learned"


# ── generate_image ────────────────────────────────────────────────

def test_generate_image_calls_remotion_cli():
    """generate_image() calls npx remotion still with correct args."""
    import subprocess
    from src import image_generator

    mock_result = MagicMock()
    mock_result.returncode = 0

    # Use a real temp file so output_path.exists() returns True naturally
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG fake")
        output_path = Path(f.name)

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = image_generator.generate_image(GOOD_PROPS, output_path=output_path)

    call_args = mock_run.call_args
    cmd = call_args[0][0]

    assert "npx" in cmd
    assert "remotion" in cmd
    assert "still" in cmd
    assert "PostCard" in cmd
    # Props JSON should be in the command
    joined = " ".join(cmd)
    assert "headline" in joined


def test_generate_image_raises_on_nonzero_exit():
    """RuntimeError if Remotion exits non-zero."""
    from src import image_generator

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Remotion compile error"
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Remotion rendering failed"):
            image_generator.generate_image(GOOD_PROPS)


def test_generate_image_raises_on_timeout():
    """RuntimeError if Remotion subprocess times out."""
    import subprocess
    from src import image_generator

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=120)):
        with pytest.raises(RuntimeError, match="timed out"):
            image_generator.generate_image(GOOD_PROPS)


def test_generate_image_raises_if_npx_missing():
    """RuntimeError if npx is not found in PATH."""
    from src import image_generator

    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="npx not found"):
            image_generator.generate_image(GOOD_PROPS)


def test_generate_image_auto_output_path():
    """If no output_path given, auto-generates in IMAGE_OUTPUT_DIR."""
    import subprocess
    from src import image_generator

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1024
                with patch("pathlib.Path.mkdir"):
                    result = image_generator.generate_image(GOOD_PROPS)

    assert result.suffix == ".png"
    assert "post_" in result.name
