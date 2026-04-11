"""
Image generation for LinkedIn posts.

Two modes (controlled by ENABLE_AI_IMAGES env var):

1. AI Image Mode (ENABLE_AI_IMAGES=true) — NEW:
   - generate_ai_post_image() generates a contextual AI image for the post
   - Pipeline: OpenRouter image API → HF FLUX.1-schnell → Remotion card fallback
   - Pillow composites a branding overlay (topic badge + handle) on the AI image

2. Remotion Mode (ENABLE_AI_IMAGES=false, default):
   - extract_image_props() extracts headline + insight (via OpenRouter, Gemini fallback)
   - generate_image() renders a branded PostCard PNG via npx remotion still
"""
import base64
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REMOTION_DIR = Path(__file__).parent.parent / "remotion"
REMOTION_ENTRY = "src/index.tsx"
REMOTION_COMPOSITION = "PostCard"

_default_image_dir = Path(__file__).parent.parent / "images"
IMAGE_OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", str(_default_image_dir)))

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/DamyTheKnightKing/linkedin-autoposter",
    "X-Title": "LinkedIn Autoposter",
}

ENABLE_AI_IMAGES = os.getenv("ENABLE_AI_IMAGES", "false").lower() == "true"


# ── AI Image Generation (new feature) ─────────────────────────────────────────

def generate_ai_post_image(post_text: str, topic: str, output_path: Optional[Path] = None) -> Path:
    """
    Generate a contextual AI image for a LinkedIn post.

    Pipeline:
        1. HuggingFace FLUX.1-schnell (free, Apache 2.0)
        2. Fallback → Remotion card (existing branded design)

    A Pillow branding overlay (topic badge + @handle) is composited on AI images.
    Returns path to the final PNG.
    """
    if output_path is None:
        IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = IMAGE_OUTPUT_DIR / f"ai_post_{int(time.time())}.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_prompt = _build_image_prompt(post_text, topic)

    raw_image: Optional[bytes] = None
    source = "remotion"

    # Layer 1: HuggingFace FLUX.1-schnell (free, Apache 2.0)
    # Note: OpenRouter does not support image generation — HF FLUX is the primary AI source.
    try:
        raw_image = _generate_image_hf_flux(image_prompt)
        source = "hf_flux"
        logger.info("AI image generated via HF FLUX.1-schnell")
    except Exception as exc:
        logger.warning("HF FLUX failed (%s), falling back to Remotion card.", exc)

    # Layer 3: Remotion card fallback
    if raw_image is None:
        logger.info("All AI image sources failed — using Remotion card fallback")
        props = extract_image_props(post_text, topic)
        return generate_image(props, output_path)

    # Save raw AI image
    output_path.write_bytes(raw_image)

    # Composite branding overlay
    try:
        _add_branding_overlay(output_path, topic, source)
        logger.info("Branding overlay applied (%s)", output_path)
    except Exception as exc:
        logger.warning("Branding overlay failed (%s) — using raw AI image", exc)

    logger.info("AI post image ready: %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path


def _build_image_prompt(post_text: str, topic: str) -> str:
    """Build a concise, visual image prompt from post content."""
    topic_map = {
        "ai_engineering": "artificial intelligence neural network abstract visualization",
        "system_design": "distributed systems architecture diagram clean minimal",
        "career_growth": "professional growth upward journey career development",
        "productivity": "focused work flow productivity minimal workspace",
        "leadership": "leadership team collaboration modern professional",
        "tech_trends": "futuristic technology digital innovation abstract",
    }
    visual_context = topic_map.get(topic, "professional technology abstract modern")

    # Extract first impactful sentence from post
    first_sentence = post_text.split(".")[0].strip()[:120]

    return (
        f"Professional LinkedIn post image: {visual_context}. "
        f"Theme: {first_sentence}. "
        "Style: Clean, modern, high-contrast, suitable for LinkedIn. "
        "No text, no words, no watermarks. Photorealistic or minimal illustration. "
        "Wide format 1200x627 aspect ratio."
    )


def _generate_image_hf_flux(prompt: str) -> bytes:
    """Generate image via HuggingFace FLUX.1-schnell (free, Apache 2.0)."""
    import requests

    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        raise RuntimeError("HF_TOKEN not set")

    url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {
        "inputs": prompt,
        "parameters": {"num_inference_steps": 4, "width": 1024, "height": 1024},
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    if resp.status_code == 503:
        raise RuntimeError("HF model loading (503) — try again in 20s")
    resp.raise_for_status()
    return resp.content


def _add_branding_overlay(image_path: Path, topic: str, source: str) -> None:
    """Add a semi-transparent topic badge and source attribution to the image."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    # Dark semi-transparent bottom bar
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bar_h = max(60, h // 10)
    draw.rectangle([(0, h - bar_h), (w, h)], fill=(0, 0, 0, 160))

    # Try to load a font, fall back to default
    try:
        font_bold  = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except OSError:
        font_bold  = ImageFont.load_default()
        font_small = font_bold

    topic_display = topic.replace("_", " ").title()

    draw.text((20, h - bar_h + 18), f"#{topic_display}", font=font_bold, fill=(255, 255, 255, 230))

    # Attribution badge (top-right)
    badge_text = "AI" if source == "hf_flux" else "Card"
    draw.rectangle([(w - 60, 10), (w - 10, 44)], fill=(79, 70, 229, 200))  # indigo
    draw.text((w - 50, 16), badge_text, font=font_small, fill=(255, 255, 255, 255))

    combined = Image.alpha_composite(img, overlay)
    combined.convert("RGB").save(image_path, "PNG")


# ── Props extraction (Remotion mode + AI image prompt) ────────────────────────

def extract_image_props(post_text: str, topic: str) -> dict:
    """
    Extract headline + insight from post for Remotion card.
    Uses OpenRouter as primary, Gemini as fallback.
    """
    try:
        return _extract_via_openrouter(post_text, topic)
    except Exception as exc:
        logger.warning("OpenRouter props extraction failed (%s). Trying Gemini...", exc)
    try:
        return _extract_via_gemini(post_text, topic)
    except Exception as exc:
        logger.warning("Gemini props extraction failed (%s). Using fallback.", exc)
        return _fallback_props(post_text, topic)


def _extract_via_openrouter(post_text: str, topic: str) -> dict:
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model   = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    client = OpenAI(
        base_url=_OPENROUTER_BASE,
        api_key=api_key,
        default_headers=_OPENROUTER_HEADERS,
    )
    prompt = _extraction_prompt(post_text)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_props_json(raw, topic)


def _extract_via_gemini(post_text: str, topic: str) -> dict:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    response = client.models.generate_content(
        model=model_name,
        config=types.GenerateContentConfig(
            max_output_tokens=200,
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        contents=_extraction_prompt(post_text),
    )
    raw = response.text.strip()
    return _parse_props_json(raw, topic)


def _extraction_prompt(post_text: str) -> str:
    return f"""You are extracting visual elements from a LinkedIn post to display on an image card.

Post text:
{post_text}

Return ONLY a JSON object with these exact keys:
- "headline": A punchy, bold title (max 10 words) that captures the post's core idea. No quotes.
- "insight": One concrete sentence (max 20 words) — the most actionable takeaway.

Example output:
{{"headline": "Stop truncating your LLM context from the end", "insight": "Keep the system prompt and last 3 turns; cut from the middle."}}

JSON only. No markdown, no explanation."""


def _parse_props_json(raw: str, topic: str) -> dict:
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
    first_sentence = post_text.split(".")[0].strip()
    headline = first_sentence[:80] if len(first_sentence) > 80 else first_sentence
    return {"headline": headline, "insight": "", "topic": topic}


# ── Remotion card rendering ────────────────────────────────────────────────────

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
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Remotion rendering timed out after 120s")
    except FileNotFoundError:
        raise RuntimeError("npx not found. Ensure Node.js is installed and in PATH.")

    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion rendering failed (exit {result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )

    if not output_path.exists():
        raise RuntimeError(f"Remotion exited 0 but output file missing: {output_path}")

    logger.info("Image rendered: %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path
