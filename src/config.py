"""Configuration loader and constants."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ── Provider ──────────────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()  # openrouter | gemini | claude

# ── OpenRouter (free — default, 200+ models) ──────────────────────────────────
OPENROUTER_API_KEY   = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL     = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-4-maverick:free")

# ── Gemini (free fallback, text-only) ─────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Anthropic (optional, paid) ────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# ── HuggingFace (free image generation fallback) ──────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")

# ── LinkedIn ──────────────────────────────────────────────────────────────────
LINKEDIN_CLIENT_ID      = os.environ["LINKEDIN_CLIENT_ID"]
LINKEDIN_CLIENT_SECRET  = os.environ["LINKEDIN_CLIENT_SECRET"]
LINKEDIN_ACCESS_TOKEN   = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_REFRESH_TOKEN  = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_TOKEN_EXPIRES_AT = os.getenv("LINKEDIN_TOKEN_EXPIRES_AT", "0")
LINKEDIN_PERSON_URN     = os.getenv("LINKEDIN_PERSON_URN", "")
LINKEDIN_REDIRECT_URI   = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback")
LINKEDIN_HANDLE         = os.getenv("LINKEDIN_HANDLE", "")

# ── Content ───────────────────────────────────────────────────────────────────
MAX_POST_LENGTH = 900
MIN_POST_LENGTH = 150
DRY_RUN         = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH      = ROOT / "posts.db"
LOG_DIR      = ROOT / "logs"
PROMPT_PATH  = ROOT / "prompts" / "post_prompt.md"
ENV_PATH     = ROOT / ".env"

# ── Topic rotation (5 categories, round-robin) ────────────────────────────────
TOPIC_CATEGORIES = [
    "ai_tips",
    "claude_features",
    "copilot_tricks",
    "data_engineering_ai",
    "lessons_learned",
]

TOPIC_DISPLAY = {
    "ai_tips":              "AI Tips & Tricks",
    "claude_features":      "Claude Features & Updates",
    "copilot_tricks":       "GitHub Copilot Tricks",
    "data_engineering_ai":  "Data Engineering + AI",
    "lessons_learned":      "Lessons Learned in AI",
}

# ── Image Generation (v3: AI image or Remotion card) ──────────────────────────
ENABLE_IMAGES    = os.getenv("ENABLE_IMAGES", "true").lower() == "true"
ENABLE_AI_IMAGES = os.getenv("ENABLE_AI_IMAGES", "false").lower() == "true"  # NEW: contextual AI images
IMAGE_OUTPUT_DIR = ROOT / os.getenv("IMAGE_OUTPUT_DIR", "images")

# ── Scheduling ────────────────────────────────────────────────────────────────
POST_HOUR   = int(os.getenv("POST_HOUR", "8"))
POST_MINUTE = int(os.getenv("POST_MINUTE", "30"))

# ── Dedup threshold ───────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.60
RECENT_POSTS_CONTEXT = 10
