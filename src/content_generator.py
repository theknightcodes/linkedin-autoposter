"""
Generate LinkedIn post content.

Supports two providers, selected by LLM_PROVIDER in .env:
  - gemini  (default, FREE) — Google Gemini 2.0 Flash, 1500 req/day free tier
  - claude  (paid)          — Anthropic Claude (sonnet / haiku)
"""
import logging
import os
import re

from src.config import (
    MAX_POST_LENGTH,
    MIN_POST_LENGTH,
    PROMPT_PATH,
    RECENT_POSTS_CONTEXT,
    TOPIC_DISPLAY,
)

COMMENT_SYSTEM_PROMPT = (
    "You are a Principal Data & AI Architect. You just published a LinkedIn post "
    "and are writing the first comment on it — within minutes of posting — to seed engagement. "
    "Your comment should add ONE extra insight, a personal example, or a sharper version of the closing question. "
    "Keep it to 1–3 sentences. Be natural, not salesy. Do NOT repeat the post. "
    "End with a direct question if the post didn't already ask one clearly enough. "
    "No hashtags. No emojis."
)

logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()


def _load_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return (
        "You are a data architect and AI practitioner with 15+ years of experience.\n"
        "You share practical, insightful LinkedIn posts about AI, Claude, GitHub Copilot, and data engineering.\n"
        "Tone: conversational, direct, technically credible — never hype, never fluff.\n"
        "Teach something concrete that practitioners can apply today."
    )


def _build_user_prompt(topic: str, recent_posts: list[str]) -> str:
    topic_label = TOPIC_DISPLAY.get(topic, topic)
    recent_context = ""
    if recent_posts:
        excerpts = [p[:200] + "…" for p in recent_posts[:RECENT_POSTS_CONTEXT]]
        recent_context = (
            "\n\nAvoid repeating these recent topics:\n"
            + "\n---\n".join(excerpts)
        )
    return f"""Write a LinkedIn post about: {topic_label}

Requirements:
- Between {MIN_POST_LENGTH} and {MAX_POST_LENGTH} characters (including hashtags)
- Start with a hook — a concrete stat, a surprising fact, or a short story
- One key insight or tip the reader can act on immediately
- Natural paragraph breaks (2–4 paragraphs)
- End with 4–6 relevant hashtags on the last line
- Do NOT use emojis as bullet points — use plain text structure
- Do NOT start with "I" — vary your openings
- Focus on practical value, not self-promotion
{recent_context}

Write only the post text. No preamble, no meta-commentary."""


# ── Gemini (free) ─────────────────────────────────────────────────

def _generate_gemini(topic: str, recent_posts: list[str]) -> str:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey"
        )

    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    system_prompt = _load_system_prompt()
    user_prompt   = _build_user_prompt(topic, recent_posts)

    response = client.models.generate_content(
        model=model_name,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1200,
            temperature=0.85,
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # disable thinking mode
        ),
        contents=user_prompt,
    )
    return response.text.strip()


# ── Claude (paid) ─────────────────────────────────────────────────

def _generate_claude(topic: str, recent_posts: list[str]) -> str:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    model   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=700,
        system=_load_system_prompt(),
        messages=[{"role": "user", "content": _build_user_prompt(topic, recent_posts)}],
    )
    return msg.content[0].text.strip()


# ── Public API ─────────────────────────────────────────────────────

def generate_post(topic: str, recent_posts: list[str]) -> str:
    """
    Generate a LinkedIn post for the given topic.
    Raises ValueError if content fails validation.
    Raises RuntimeError if the provider is misconfigured.
    """
    logger.info("Generating post — provider: %s, topic: %s", PROVIDER, topic)

    if PROVIDER == "gemini":
        text = _generate_gemini(topic, recent_posts)
    elif PROVIDER == "claude":
        text = _generate_claude(topic, recent_posts)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{PROVIDER}'. Use 'gemini' or 'claude'.")

    _validate(text, topic)
    return text


def generate_comment(post_text: str) -> str:
    """Generate a short follow-up comment to post on the published LinkedIn post."""
    user_prompt = (
        f"Here is the LinkedIn post I just published:\n\n{post_text}\n\n"
        "Write a short follow-up comment (1–3 sentences) to post as the first comment. "
        "Add a new angle, a concrete personal example, or sharpen the question. No hashtags."
    )
    try:
        if PROVIDER == "gemini":
            from google import genai
            from google.genai import types
            api_key = os.environ.get("GEMINI_API_KEY", "")
            client  = genai.Client(api_key=api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            response = client.models.generate_content(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=COMMENT_SYSTEM_PROMPT,
                    max_output_tokens=200,
                    temperature=0.8,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
                contents=user_prompt,
            )
            return response.text.strip()
        else:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            model   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
            client  = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model,
                max_tokens=200,
                system=COMMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return msg.content[0].text.strip()
    except Exception as exc:
        logger.warning("Comment generation failed: %s", exc)
        return ""


def _validate(text: str, topic: str) -> None:
    length = len(text)
    if length < MIN_POST_LENGTH:
        raise ValueError(f"Post too short ({length} chars, min {MIN_POST_LENGTH}). Topic: {topic}")
    if length > MAX_POST_LENGTH:
        raise ValueError(f"Post too long ({length} chars, max {MAX_POST_LENGTH}). Topic: {topic}")
    hashtags = re.findall(r"#\w+", text)
    if len(hashtags) < 3:
        raise ValueError(f"Post has only {len(hashtags)} hashtags (need ≥ 3). Topic: {topic}")
    logger.debug("Post validated: %d chars, %d hashtags", length, len(hashtags))
