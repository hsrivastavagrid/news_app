import pytest
from app.services.news_fetcher import generate_mock_articles, compute_url_hash

def test_url_hash_uniqueness():
    h1 = compute_url_hash("https://example.com/news-1")
    h2 = compute_url_hash("https://example.com/news-2")
    assert h1 != h2
    assert len(h1) == 64

def test_mock_articles_generation():
    articles = generate_mock_articles("technology")
    assert len(articles) > 0
    assert articles[0].api_category == "technology"
    assert "tech" in articles[0].url or "example" in articles[0].url
