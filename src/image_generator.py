"""
Image generation using Remotion (React → PNG).

Flow:
  1. extract_image_props()  — Gemini extracts headline + insight from post text
  2. generate_image()       — shells out to `npx remotion still` in the remotion/ subdir
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Remotion project lives one level up from src/
REMOTION_DIR = Path(__file__).parent.parent / "remotion"
REMOTION_ENTRY = "src/index.tsx"
REMOTION_COMPOSITION = "PostCard"

# Where to store generated images (override with IMAGE_OUTPUT_DIR env var)
_default_image_dir = Path(__file__).parent.parent / "images"
IMAGE_OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", str(_default_image_dir)))


def extract_image_props(post_text: str, topic: str) -> dict:
    """
    Use Gemini to extract a short headline and one-sentence insight from the post.
    Returns a dict with keys: headline, insight, topic.
    Falls back to a basic truncation if Gemini call fails.
    """
    try:
        return _extract_via_gemini(post_text, topic)
    except Exception as exc:
        logger.warning("Gemini image-props extraction failed (%s). Using fallback.", exc)
        return _fallback_props(post_text, topic)


def _extract_via_gemini(post_text: str, topic: str) -> dict:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    prompt = f"""You are extracting visual elements from a LinkedIn post to display on an image card.

Post text:
{post_text}

Return ONLY a JSON object with these exact keys:
- "headline": A punchy, bold title (max 10 words) that captures the post's core idea. No quotes.
- "insight": One concrete sentence (max 20 words) — the most actionable takeaway.

Example output:
{{"headline": "Stop truncating your LLM context from the end", "insight": "Keep the system prompt and last 3 turns; cut from the middle."}}

JSON only. No markdown, no explanation."""

    response = client.models.generate_content(
        model=model_name,
        config=types.GenerateContentConfig(
            max_output_tokens=200,
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        contents=prompt,
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.startswith("```")
        ).strip()

    props = json.loads(raw)
    props["topic"] = topic
    logger.debug("Extracted image props: %s", props)
    return props


def _fallback_props(post_text: str, topic: str) -> dict:
    """Basic fallback: use first sentence as headline."""
    first_sentence = post_text.split(".")[0].strip()
    headline = first_sentence[:80] if len(first_sentence) > 80 else first_sentence
    return {
        "headline": headline,
        "insight": "",
        "topic": topic,
    }


def generate_image(props: dict, output_path: Optional[Path] = None) -> Path:
    """
    Render a PostCard PNG using the Remotion CLI.

    Args:
        props: dict with headline, insight, topic (and optionally author)
        output_path: where to save the PNG; auto-generated if None

    Returns:
        Path to the rendered PNG file.

    Raises:
        RuntimeError if Remotion rendering fails.
    """
    if output_path is None:
        IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        import time
        output_path = IMAGE_OUTPUT_DIR / f"post_{int(time.time())}.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    props_json = json.dumps(props)

    cmd = [
        "npx", "remotion", "still",
        REMOTION_ENTRY,
        REMOTION_COMPOSITION,
        str(output_path),
        f"--props={props_json}",
    ]

    logger.info("Rendering image card: %s", output_path)
    logger.debug("Remotion command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=120,  # Remotion can take time on first run (downloads Chrome)
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Remotion rendering timed out after 120s")
    except FileNotFoundError:
        raise RuntimeError(
            "npx not found. Ensure Node.js is installed and in PATH."
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion rendering failed (exit {result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )

    if not output_path.exists():
        raise RuntimeError(f"Remotion exited 0 but output file missing: {output_path}")

    logger.info("Image rendered: %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path
