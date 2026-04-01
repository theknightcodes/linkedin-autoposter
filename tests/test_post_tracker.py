"""Tests for post_tracker — uses in-memory SQLite."""
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── Redirect DB to a temp file ────────────────────────────────────
@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_posts.db"
    monkeypatch.setattr("src.config.DB_PATH", db_path)
    # Re-import tracker so it picks up the patched path
    import src.post_tracker as tracker
    importlib.reload(tracker)
    tracker.init_db()
    yield tracker


def test_init_creates_table(tmp_db):
    stats = tmp_db.get_stats()
    assert stats["total"] == 0


def test_topic_rotation_cycles(tmp_db):
    from src.config import TOPIC_CATEGORIES
    for i, expected in enumerate(TOPIC_CATEGORIES):
        # Record a successful post for previous topic
        if i > 0:
            tmp_db.record_post(TOPIC_CATEGORIES[i - 1], f"post {i}", "posted")
        assert tmp_db.get_next_topic() == TOPIC_CATEGORIES[i]

    # After full cycle, wraps back to first
    tmp_db.record_post(TOPIC_CATEGORIES[-1], "last post", "posted")
    assert tmp_db.get_next_topic() == TOPIC_CATEGORIES[0]


def test_duplicate_detection_exact(tmp_db):
    text = "This is a test post about Claude AI features. #AI #Claude"
    tmp_db.record_post("claude_features", text, "posted")
    assert tmp_db.is_duplicate(text) is True


def test_duplicate_detection_similar(tmp_db):
    text_a = "Claude's extended thinking mode lets you trace reasoning step by step. Great for debugging prompts. #AI #Claude"
    text_b = "Claude extended thinking mode lets trace reasoning step by step. Perfect debugging prompts. #AI #Claude"
    tmp_db.record_post("claude_features", text_a, "posted")
    assert tmp_db.is_duplicate(text_b) is True


def test_unique_post_not_flagged(tmp_db):
    text_a = "dbt staging models should never contain joins. Caught that one late. #dbt #DataEngineering"
    text_b = "GitHub Copilot /fix command is underrated. It explains the fix too, not just applies it. #Copilot #AI"
    tmp_db.record_post("lessons_learned", text_a, "posted")
    assert tmp_db.is_duplicate(text_b) is False


def test_record_and_update(tmp_db):
    row_id = tmp_db.record_post("ai_tips", "Test post", "pending")
    assert row_id > 0
    tmp_db.update_post_status(row_id, "posted", linkedin_urn="urn:li:share:123")
    stats = tmp_db.get_stats()
    assert stats["posted"] == 1


def test_get_recent_posts(tmp_db):
    for i in range(5):
        tmp_db.record_post("ai_tips", f"Post number {i} about AI tools.", "posted")
    recent = tmp_db.get_recent_posts(3)
    assert len(recent) == 3


def test_stats_accuracy(tmp_db):
    tmp_db.record_post("ai_tips", "post 1", "posted")
    tmp_db.record_post("claude_features", "post 2", "failed", error="timeout")
    tmp_db.record_post("copilot_tricks", "post 3", "posted")
    s = tmp_db.get_stats()
    assert s["total"] == 3
    assert s["posted"] == 2
    assert s["failed"] == 1
    assert s["success_rate"] == pytest.approx(66.7, abs=0.1)
