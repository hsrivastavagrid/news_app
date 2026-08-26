from typing import Optional
from urllib.parse import urlparse


def is_placeholder_url(url: Optional[str]) -> bool:
    """True when the URL is not a publisher article (mocks, synth, old Google-search fallback)."""
    if not url:
        return True
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
    except ValueError:
        return True
    if parsed.scheme not in ("http", "https"):
        return True
    if host == "example.com" or host.endswith(".example.com"):
        return True
    if "newsapi.org" in host and "/articles/synth-" in url:
        return True
    if host in {"news.google.com", "www.news.google.com"} and path.startswith("/search"):
        return True
    return False


def source_article_url(url: Optional[str]) -> Optional[str]:
    """Publisher URL from the fetch. None if there is no real article page."""
    if is_placeholder_url(url):
        return None
    return url
