"""
Orchestrator entry point — v3 (AI images + OpenRouter).

Usage:
    python -m src.main              # generate + image + post to LinkedIn
    python -m src.main --dry-run    # generate + print, do NOT post
    python -m src.main --no-image   # skip image generation, post text-only
    python -m src.main --stats      # print posting statistics

Image mode is controlled by ENABLE_AI_IMAGES env var:
    ENABLE_AI_IMAGES=true  — generate contextual AI image (OpenRouter → HF FLUX → Remotion)
    ENABLE_AI_IMAGES=false — render branded Remotion card (default)
"""
import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "autoposter.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("main")


def run(dry_run: bool = False, no_image: bool = False) -> None:
    from src import config
    from src.post_tracker import (
        init_db,
        get_next_topic,
        is_duplicate,
        get_recent_posts,
        record_post,
        update_post_status,
    )
    from src.content_generator import generate_post
    from src.linkedin_client import create_post, upload_image
    from src.token_manager import get_valid_token

    dry_run = dry_run or config.DRY_RUN
    images_enabled = config.ENABLE_IMAGES and not no_image

    if dry_run:
        logger.info("DRY RUN mode — will not post to LinkedIn")
    if not images_enabled:
        logger.info("Image generation disabled")

    # 1. Initialise DB
    init_db()

    # 2. Validate token early (fail fast if auth is broken)
    if not dry_run:
        logger.info("Validating LinkedIn token…")
        get_valid_token()   # raises if expired / missing

    # 3. Determine topic
    topic = get_next_topic()
    logger.info("Next topic: %s", topic)

    # 4. Generate content (up to 3 attempts for variety)
    post_text: str | None = None
    for attempt in range(1, 4):
        logger.info("Generating post (attempt %d)…", attempt)
        try:
            candidate = generate_post(topic, get_recent_posts())
        except ValueError as exc:
            logger.warning("Validation failed: %s", exc)
            continue

        if is_duplicate(candidate):
            logger.warning("Duplicate detected on attempt %d. Regenerating.", attempt)
            continue

        post_text = candidate
        break

    if post_text is None:
        logger.error("Could not generate a unique, valid post after 3 attempts.")
        record_post(topic, "(generation failed)", "failed", error="3 failed generation attempts")
        sys.exit(1)

    logger.info("Generated post (%d chars):\n%s", len(post_text), post_text)

    # 5. Generate image card (v3 — AI image or Remotion card)
    image_path = None
    if images_enabled:
        try:
            from src.image_generator import ENABLE_AI_IMAGES, generate_ai_post_image, extract_image_props, generate_image
            if ENABLE_AI_IMAGES:
                logger.info("Generating AI post image (ENABLE_AI_IMAGES=true)…")
                image_path = generate_ai_post_image(post_text, topic)
            else:
                logger.info("Extracting image props from post…")
                image_props = extract_image_props(post_text, topic)
                logger.info("Rendering image card (headline: %s)…", image_props.get("headline", ""))
                image_path = generate_image(image_props)
        except Exception as exc:
            logger.warning("Image generation failed — continuing with text-only post. Error: %s", exc)
            image_path = None

    # 6. Dry-run exit
    if dry_run:
        print("\n" + "─" * 60)
        print(f"TOPIC: {topic}")
        print("─" * 60)
        print(post_text)
        if image_path:
            print(f"\n🖼  Image card: {image_path}")
        print("─" * 60 + "\n")
        print("✅ Dry run complete. Not posted.")
        return

    # 7. Post to LinkedIn (with optional image)
    person_urn = os.environ.get("LINKEDIN_PERSON_URN", "")
    row_id = record_post(topic, post_text, "pending")

    try:
        image_urn: str | None = None

        if image_path:
            try:
                logger.info("Uploading image to LinkedIn…")
                image_urn = upload_image(image_path, person_urn)
                logger.info("Image uploaded. URN: %s", image_urn)
            except Exception as exc:
                logger.warning("Image upload failed — posting text-only. Error: %s", exc)
                image_urn = None

        urn = create_post(post_text, person_urn, image_urn=image_urn)
        update_post_status(row_id, "posted", linkedin_urn=urn, image_urn=image_urn)
        logger.info("✅ Posted successfully. LinkedIn URN: %s%s", urn,
                    f" | Image URN: {image_urn}" if image_urn else " (text-only)")

    except Exception as exc:
        update_post_status(row_id, "failed", error=str(exc))
        logger.error("❌ Post failed: %s", exc)
        sys.exit(1)


def show_stats() -> None:
    from src.post_tracker import init_db, get_stats
    from src.config import TOPIC_DISPLAY

    init_db()
    s = get_stats()
    print("\n" + "═" * 40)
    print("  LinkedIn Autoposter — Stats")
    print("═" * 40)
    print(f"  Total runs    : {s['total']}")
    print(f"  Posted        : {s['posted']}")
    print(f"  Failed        : {s['failed']}")
    print(f"  Success rate  : {s['success_rate']}%")
    print(f"  Last post     : {s['last_post_at'] or 'never'}")
    print(f"  Last topic    : {s['last_post_topic'] or '—'}")
    print(f"  Next topic    : {s['next_topic']}")
    print("\n  Posts by topic:")
    for cat, disp in TOPIC_DISPLAY.items():
        count = s["by_topic"].get(cat, 0)
        print(f"    {disp:<30} {count}")
    print("═" * 40 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn AI daily poster — v2 with image cards")
    parser.add_argument("--dry-run",  action="store_true", help="Generate but do not post")
    parser.add_argument("--no-image", action="store_true", help="Skip image generation, post text-only")
    parser.add_argument("--stats",    action="store_true", help="Print statistics and exit")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    run(dry_run=args.dry_run, no_image=args.no_image)


if __name__ == "__main__":
    main()
