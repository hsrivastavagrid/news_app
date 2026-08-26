import pytest
from app.models import RawArticle
from app.urls import source_article_url
from app.services.news_fetcher import (
    compute_url_hash,
    normalize_published_at,
    canonicalize_url,
    dedupe_fetch_batch,
    title_fingerprint,
)

def test_url_hash_uniqueness():
    h1 = compute_url_hash("https://example.com/news-1")
    h2 = compute_url_hash("https://example.com/news-2")
    assert h1 != h2
    assert len(h1) == 64

def test_normalize_published_at_iso_z():
    out = normalize_published_at("2026-08-26T15:04:05Z")
    assert out == "2026-08-26 15:04:05"

def test_source_article_url_drops_placeholders():
    assert source_article_url("https://tech.example.com/ai-chip-1") is None
    assert source_article_url("https://news.google.com/search?q=ai") is None

def test_source_article_url_keeps_publisher():
    real = "https://www.reuters.com/world/story-1"
    assert source_article_url(real) == real

def _raw(title, url, description=""):
    return RawArticle(
        title=title,
        description=description,
        url=url,
        source_name="Wire",
        api_category="general",
        image_url=None,
        published_at="2026-08-26 10:00:00",
        url_hash=compute_url_hash(url),
    )

def test_canonicalize_url_strips_tracking():
    a = canonicalize_url("http://www.Reuters.com/world/story/?utm_source=x&id=1")
    b = canonicalize_url("https://reuters.com/world/story?id=1")
    assert a == b
    assert compute_url_hash("https://reuters.com/world/story?utm_medium=rss&id=1") == compute_url_hash(
        "https://www.reuters.com/world/story/?id=1"
    )

def test_dedupe_fetch_batch_collapses_url_and_title():
    batch = [
        _raw("Central banks raise rates amid inflation", "https://a.com/1?utm_source=feed", "short"),
        _raw("Central banks raise rates amid inflation", "https://b.com/other", "much longer description here"),
        _raw("Unrelated glacier study published today", "https://c.com/ice"),
    ]
    kept = dedupe_fetch_batch(batch)
    titles = {a.title for a in kept}
    assert len(kept) == 2
    assert "Central banks raise rates amid inflation" in titles
    rates = next(a for a in kept if "Central" in a.title)
    assert rates.description.startswith("much longer")

def test_title_fingerprint_strips_cycle():
    assert title_fingerprint("AI Chip Breakthrough (Cycle 12)") == title_fingerprint("AI Chip Breakthrough")


