"""SQLite-backed post history, deduplication, and topic rotation."""
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import DB_PATH, TOPIC_CATEGORIES, SIMILARITY_THRESHOLD


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the posts table if it doesn't exist, and migrate existing tables."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                topic         TEXT    NOT NULL,
                content_hash  TEXT    NOT NULL,
                content_text  TEXT    NOT NULL,
                linkedin_urn  TEXT,
                image_urn     TEXT,
                status        TEXT    NOT NULL DEFAULT 'pending',
                created_at    TEXT    NOT NULL,
                posted_at     TEXT,
                error_message TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON posts(content_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON posts(status)")

        # Migration: add image_urn column to existing databases
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(posts)").fetchall()
        }
        if "image_urn" not in existing_cols:
            conn.execute("ALTER TABLE posts ADD COLUMN image_urn TEXT")

        conn.commit()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def get_next_topic() -> str:
    """Return the next topic in round-robin based on successful post count."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM posts WHERE status = 'posted'"
        ).fetchone()
        count = row["cnt"] if row else 0
    return TOPIC_CATEGORIES[count % len(TOPIC_CATEGORIES)]


def is_duplicate(text: str, recent_n: int = 20) -> bool:
    """
    Return True if the text is a near-duplicate of any recent post.
    Uses exact hash check first, then Jaccard similarity.
    """
    h = _hash(text)
    with _connect() as conn:
        # Exact match
        row = conn.execute(
            "SELECT 1 FROM posts WHERE content_hash = ?", (h,)
        ).fetchone()
        if row:
            return True

        # Similarity check against recent posts
        rows = conn.execute(
            "SELECT content_text FROM posts ORDER BY id DESC LIMIT ?", (recent_n,)
        ).fetchall()

    for row in rows:
        if _jaccard(text, row["content_text"]) >= SIMILARITY_THRESHOLD:
            return True
    return False


def get_recent_posts(n: int = 10) -> list[str]:
    """Return the last n post texts for Claude context."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT content_text FROM posts WHERE status = 'posted' ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [r["content_text"] for r in rows]


def record_post(
    topic: str,
    text: str,
    status: str,
    linkedin_urn: Optional[str] = None,
    image_urn: Optional[str] = None,
    error: Optional[str] = None,
) -> int:
    """Insert a post record. Returns the new row id."""
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (topic, content_hash, content_text, linkedin_urn,
                               image_urn, status, created_at, posted_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic,
                _hash(text),
                text,
                linkedin_urn,
                image_urn,
                status,
                now,
                now if status == "posted" else None,
                error,
            ),
        )
        conn.commit()
        return cur.lastrowid


def update_post_status(
    row_id: int,
    status: str,
    linkedin_urn: Optional[str] = None,
    image_urn: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE posts
            SET status = ?, linkedin_urn = ?, image_urn = ?, posted_at = ?, error_message = ?
            WHERE id = ?
            """,
            (status, linkedin_urn, image_urn, now if status == "posted" else None, error, row_id),
        )
        conn.commit()


def get_stats() -> dict:
    """Return a summary dict useful for debugging and monitoring."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
        posted = conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status='posted'"
        ).fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status='failed'"
        ).fetchone()["c"]

        by_topic = {
            row["topic"]: row["c"]
            for row in conn.execute(
                "SELECT topic, COUNT(*) AS c FROM posts WHERE status='posted' GROUP BY topic"
            ).fetchall()
        }

        last_post = conn.execute(
            "SELECT posted_at, topic FROM posts WHERE status='posted' ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return {
        "total": total,
        "posted": posted,
        "failed": failed,
        "success_rate": round(posted / total * 100, 1) if total else 0,
        "by_topic": by_topic,
        "last_post_at": last_post["posted_at"] if last_post else None,
        "last_post_topic": last_post["topic"] if last_post else None,
        "next_topic": get_next_topic(),
    }
