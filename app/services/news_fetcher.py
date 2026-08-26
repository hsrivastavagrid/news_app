import hashlib
import logging
import time
import re
import datetime
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import httpx

from app.config import (
    NEWSAPI_KEY,
    CURRENTS_API_KEY,
    NEWSAPI_BASE_URL,
    NEWSAPI_EVERYTHING_URL,
    CURRENTS_BASE_URL,
    CATEGORY_TO_TAG,
    TAG_KEYWORDS,
    DOMAIN_TAGS,
)
from app.models import RawArticle
from app.services.sentiment_analyzer import analyze_text
from app.database import db

logger = logging.getLogger("newspulse.fetcher")

TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_reader", "fbclid", "gclid", "mc_cid", "mc_eid",
    "igshid", "si", "ref", "referrer", "source", "ocid", "ns_campaign",
}

def canonicalize_url(url: Optional[str]) -> str:
    """Strip tracking params / fragments so the same story URL hashes identically."""
    if not url:
        return ""
    raw = url.strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw.lower()
    scheme = (parsed.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"
    kept = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in TRACKING_QUERY_KEYS:
            continue
        kept.append((key, value))
    query = urlencode(sorted(kept), doseq=True)
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    return urlunparse((scheme, netloc, path, "", query, ""))


def compute_url_hash(url: str) -> str:
    """SHA256 of the canonical URL for fetch- and store-time dedup."""
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def title_fingerprint(title: Optional[str]) -> str:
    """Normalize headline so republished copies collapse in one fetch."""
    text = re.sub(r"\s*\(Cycle \d+\)\s*$", "", title or "", flags=re.I)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return text

def normalize_published_at(raw: Optional[str]) -> str:
    """Store UTC as 'YYYY-MM-DD HH:MM:SS' so SQLite datetime() window filters match."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if not raw:
        return now.strftime("%Y-%m-%d %H:%M:%S")
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return now.strftime("%Y-%m-%d %H:%M:%S")

def assign_tags(api_category: Optional[str], title: str, description: Optional[str]) -> List[str]:
    """Assigns MULTIPLE domain tags to an article based on category and keyword matches."""
    tags = set()
    full_text = f"{title} {description or ''}".lower()

    # 1. Base tag from API category mapping
    if api_category:
        base_tag = CATEGORY_TO_TAG.get(api_category.lower())
        if base_tag and base_tag in DOMAIN_TAGS:
            tags.add(base_tag)

    # 2. Keyword matching across all domain tags
    for tag_name, keywords in TAG_KEYWORDS.items():
        hits = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw), full_text):
                hits += 1
        if hits >= 2:
            tags.add(tag_name)

    # 3. Fallback to general if no specific tag matched
    if not tags:
        tags.add("general")

    return sorted(list(tags))

# NewsAPI.org category names
# https://newsapi.org/docs/endpoints/top-headlines
# Valid categories: business, entertainment, general, health, science, sports, technology
NEWSAPI_CATEGORIES = [
    "general",
    "business",
    "technology",
    "entertainment",
    "sports",
    "science",
    "health",
]

# Map NewsAPI categories to our internal CATEGORY_TO_TAG keys
NEWSAPI_CATEGORY_MAP = {
    "general": "general",
    "business": "business",
    "technology": "technology",
    "entertainment": "entertainment",
    "sports": "sports",
    "science": "science",
    "health": "health",
}

def fetch_from_newsapi(category: Optional[str] = None) -> List[RawArticle]:
    """Fetches top headlines from NewsAPI.org for a rolling 1-hour window (now - 1 hour -> now).
    
    Makes a single API call for up to 100 top headlines to minimize requests and prevent 429 rate limiting.
    """
    if not NEWSAPI_KEY:
        logger.info("newsapi headlines skipped: NEWSAPI_KEY not set")
        return []

    # Compute rolling 1-hour window: (now - 1h) -> now
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_utc = now_utc - datetime.timedelta(hours=1)
    start_iso = start_utc.isoformat()

    params = {
        "language": "en",
        "pageSize": 100,
        "apiKey": NEWSAPI_KEY,
        "from": start_iso,
    }
    if category:
        params["category"] = category

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(NEWSAPI_BASE_URL, params=params)
            if resp.status_code == 426:
                logger.error("newsapi 426 upgrade required category=%s", category)
                return []
            if resp.status_code == 429:
                logger.warning("newsapi rate limited 429 category=%s", category)
                return []
            if resp.status_code != 200:
                logger.error(
                    "newsapi headlines error status=%s category=%s body=%s",
                    resp.status_code,
                    category,
                    resp.text[:200],
                )
                return []
            data = resp.json()
            if data.get("status") != "ok":
                logger.error("newsapi non-ok status message=%s", data.get("message", ""))
                return []

            articles = []
            for item in data.get("articles", []):
                art_url = item.get("url")
                title = item.get("title") or ""
                # NewsAPI sometimes returns "[Removed]" placeholder articles
                if not art_url or title == "[Removed]":
                    continue
                
                # Standardize publishedAt timestamp
                pub_raw = item.get("publishedAt") or now_utc.isoformat()
                articles.append(
                    RawArticle(
                        title=title,
                        description=item.get("description"),
                        url=art_url,
                        source_name=(item.get("source") or {}).get("name"),
                        api_category=NEWSAPI_CATEGORY_MAP.get(category, category) if category else "general",
                        image_url=item.get("urlToImage"),
                        published_at=pub_raw,
                        url_hash=compute_url_hash(art_url),
                    )
                )
            logger.info("newsapi headlines category=%s count=%s", category or "all", len(articles))
            return articles
    except Exception:
        logger.exception("newsapi headlines failed category=%s", category)
        return []


def fetch_from_newsapi_markets() -> List[RawArticle]:
    """Second everything query biased to issuers, earnings, rates, and tape-moving events."""
    if not NEWSAPI_KEY:
        logger.info("newsapi markets skipped: NEWSAPI_KEY not set")
        return []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_iso = (now_utc - datetime.timedelta(hours=1)).isoformat()
    params = {
        "q": (
            'earnings OR "interest rate" OR Nasdaq OR "S&P" OR "Wall Street" OR '
            "IPO OR merger OR dividend OR Fed OR FOMC OR shares OR investor OR "
            "downgrade OR upgrade OR bankruptcy OR layoff OR Tesla OR NVIDIA OR Apple"
        ),
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
        "from": start_iso,
        "apiKey": NEWSAPI_KEY,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(NEWSAPI_EVERYTHING_URL, params=params)
            if resp.status_code != 200:
                logger.error(
                    "newsapi markets error status=%s body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
                return []
            data = resp.json()
            articles = []
            for item in data.get("articles", []):
                art_url = item.get("url")
                title = item.get("title") or ""
                if not art_url or title == "[Removed]":
                    continue
                articles.append(
                    RawArticle(
                        title=title,
                        description=item.get("description"),
                        url=art_url,
                        source_name=(item.get("source") or {}).get("name"),
                        api_category="business",
                        image_url=item.get("urlToImage"),
                        published_at=item.get("publishedAt") or now_utc.isoformat(),
                        url_hash=compute_url_hash(art_url),
                    )
                )
            logger.info("newsapi markets count=%s", len(articles))
            return articles
    except Exception:
        logger.exception("newsapi markets failed")
        return []


def fetch_from_newsapi_everything() -> List[RawArticle]:
    """Pull a large recent pool from NewsAPI /everything for the last hour."""
    if not NEWSAPI_KEY:
        logger.info("newsapi everything skipped: NEWSAPI_KEY not set")
        return []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_iso = (now_utc - datetime.timedelta(hours=1)).isoformat()
    params = {
        "q": "news OR world OR economy OR technology OR health OR sports OR science",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
        "from": start_iso,
        "apiKey": NEWSAPI_KEY,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(NEWSAPI_EVERYTHING_URL, params=params)
            if resp.status_code != 200:
                logger.error(
                    "newsapi everything error status=%s body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
                return []
            data = resp.json()
            articles = []
            for item in data.get("articles", []):
                art_url = item.get("url")
                title = item.get("title") or ""
                if not art_url or title == "[Removed]":
                    continue
                articles.append(
                    RawArticle(
                        title=title,
                        description=item.get("description"),
                        url=art_url,
                        source_name=(item.get("source") or {}).get("name"),
                        api_category="general",
                        image_url=item.get("urlToImage"),
                        published_at=item.get("publishedAt") or now_utc.isoformat(),
                        url_hash=compute_url_hash(art_url),
                    )
                )
            logger.info("newsapi everything count=%s", len(articles))
            return articles
    except Exception:
        logger.exception("newsapi everything failed")
        return []

def fetch_from_currents(category: str) -> List[RawArticle]:
    """Fallback fetch from Currents API."""
    if not CURRENTS_API_KEY:
        logger.info("currents skipped: CURRENTS_API_KEY not set")
        return []

    url = f"{CURRENTS_BASE_URL}?language=en&apiKey={CURRENTS_API_KEY}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.error("currents error status=%s body=%s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()
            articles = []
            for item in data.get("news", []):
                art_url = item.get("url")
                if not art_url:
                    continue
                articles.append(
                    RawArticle(
                        title=item.get("title", ""),
                        description=item.get("description"),
                        url=art_url,
                        source_name=item.get("author") or "Currents News",
                        api_category=category,
                        image_url=item.get("image"),
                        published_at=item.get("published"),
                        url_hash=compute_url_hash(art_url),
                    )
                )
            logger.info("currents count=%s", len(articles))
            return articles
    except Exception:
        logger.exception("currents fetch failed")
        return []

def generate_mock_articles(category: str = "general") -> List[RawArticle]:
    """Synthetic headlines used when live APIs return nothing (rolling 1-hour timestamps)."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    mock_time = now_utc - datetime.timedelta(minutes=30)
    mock_iso = mock_time.strftime("%Y-%m-%d %H:%M:%S")
    unique_ns = time.time_ns()

    samples = {
        "general": [
            ("Global Summit Reaches Landmark Accord on Renewable Energy", "World leaders agree to triple clean energy capacity in historic climate pact.", "https://news.example.com/global-climate-accord"),
            ("Unprecedented Weather Prompts Emergency Responses Across Continents", "Severe disruptions impact infrastructure and agriculture worldwide.", "https://news.example.com/global-weather-disruption"),
        ],
        "business": [
            ("Central Banks Signal Monetary Adjustments as Economic Indicators Shift", "Financial markets adjust following unexpected interest rate policy updates.", "https://finance.example.com/central-bank-rate-update"),
            ("Major Financial Institution Faces Regulatory Investigation", "Regulators inspect financial accounting records, impacting market sentiment.", "https://finance.example.com/bank-investigation"),
        ],
        "technology": [
            ("Breakthrough Artificial Intelligence Chip Achieves Record Efficiency", "Technology pioneer unveils next-generation semiconductor architecture.", "https://tech.example.com/ai-chip-breakthrough"),
            ("Cybersecurity Alert Issued Following Platform Zero-Day Vulnerability", "Security researchers discover zero-day vulnerability in cloud infrastructure.", "https://tech.example.com/zero-day-vulnerability"),
        ],
        "health": [
            ("Medical Trial Reports Significant Progress in Target Therapy", "Clinical trials demonstrate positive outcomes for novel treatment protocols.", "https://health.example.com/medical-trial-progress"),
            ("Health Advisory Issued Following Seasonal Viral Outbreak", "Healthcare facilities implement elevated safety measures during outbreak.", "https://health.example.com/health-advisory-outbreak"),
        ],
        "sports": [
            ("Championship Match Concludes in Thrilling Overtime Victory", "Athletic tournament finishes with remarkable team performance.", "https://sports.example.com/championship-overtime-victory"),
            ("Sports League Announces Updates to Conduct and Compliance Guidelines", "Regulatory committee updates league policies following review.", "https://sports.example.com/sports-league-guidelines"),
        ],
        "science": [
            ("Space Telescope Observes Atmospheric Composition of Nearby Exoplanet", "Astronomers publish compelling research on exoplanetary atmosphere findings.", "https://science.example.com/exoplanet-atmosphere-discovery"),
            ("Environmental Researchers Publish Major Study on Glacier Dynamics", "Scientists analyze satellite data tracking polar ice layer transformations.", "https://science.example.com/glacier-dynamics-study"),
        ],
        "entertainment": [
            ("International Film Festival Announces Winners of Top Awards", "Cinematic festival celebrates outstanding achievements in direction and performance.", "https://ent.example.com/film-festival-winners"),
            ("Music Industry Summit Discusses Future of Streaming and Licensing", "Industry leaders gather to establish new frameworks for digital distribution.", "https://ent.example.com/music-industry-summit"),
        ],
    }

    item_list = samples.get(category, samples["general"])
    raw_list = []
    for idx, (title, desc, base_url) in enumerate(item_list):
        timestamped_url = f"{base_url}-{unique_ns}-{idx}"
        dynamic_title = f"{title} (Cycle {unique_ns % 10000})"
        raw_list.append(
            RawArticle(
                title=dynamic_title,
                description=desc,
                url=timestamped_url,
                source_name="NewsPulse Global Service",
                api_category=category,
                image_url=None,
                published_at=mock_iso,
                url_hash=compute_url_hash(timestamped_url),
            )
        )
    return raw_list

def process_raw_articles(
    raw_articles: List[RawArticle],
    fetched_at: Optional[str] = None,
) -> int:
    """
    Core processing pipeline:
    1. Analyzes sentiment using sentiment_analyzer.analyze_text()
    2. Assigns multi-domain tags using assign_tags()
    3. Stores articles into SQLite database via db.insert_article()
    4. Computes hourly tag snapshots & triggers contagion detection
    """
    from app.services.market_desk import finance_tags_for

    total_new_articles = 0
    raw_articles = dedupe_fetch_batch(raw_articles)
    logger.info("process batch after in-fetch dedupe count=%s", len(raw_articles))

    for raw in raw_articles:
        raw.published_at = normalize_published_at(raw.published_at)
        raw.url_hash = compute_url_hash(raw.url)
        # 1. Analyze sentiment via sentiment_analyzer.py
        sentiment = analyze_text(raw.title, raw.description)

        # 2. Assign domain tags locally via keyword matching (+ finance if issuers)
        tags = finance_tags_for(
            raw.title,
            raw.description,
            assign_tags(raw.api_category, raw.title, raw.description),
        )

        # 3. Store in DB
        try:
            article_id = db.insert_article(raw, sentiment, tags, fetched_at=fetched_at)
            if article_id:
                total_new_articles += 1
                logger.debug("article stored id=%s tags=%s label=%s", article_id, tags, sentiment.label)
        except Exception:
            logger.exception("article store failed url=%s", raw.url)

    # 4. Generate hourly snapshots
    db.create_hourly_tag_snapshots()

    return total_new_articles

def _prefer_article(current: RawArticle, incoming: RawArticle) -> RawArticle:
    """Keep the richer copy when two items are the same story."""
    cur_len = len(current.description or "")
    inc_len = len(incoming.description or "")
    if inc_len > cur_len:
        return incoming
    if not current.image_url and incoming.image_url:
        return incoming
    return current


def dedupe_fetch_batch(articles: List[RawArticle]) -> List[RawArticle]:
    """
    Deduplicate one fetch cycle:
    1) canonical URL (tracking params, www, trailing slash)
    2) normalized headline (same wire story, different publishers)
    """
    by_url = {}
    dropped_url = 0
    for art in articles:
        art.url_hash = compute_url_hash(art.url)
        existing = by_url.get(art.url_hash)
        if existing is None:
            by_url[art.url_hash] = art
        else:
            dropped_url += 1
            by_url[art.url_hash] = _prefer_article(existing, art)

    by_title = {}
    dropped_title = 0
    for art in by_url.values():
        fp = title_fingerprint(art.title)
        if len(fp) < 24:
            # Short/generic titles are too collision-prone; URL key is enough.
            by_title[f"url:{art.url_hash}"] = art
            continue
        existing = by_title.get(fp)
        if existing is None:
            by_title[fp] = art
        else:
            dropped_title += 1
            by_title[fp] = _prefer_article(existing, art)

    kept = list(by_title.values())
    logger.info(
        "in-fetch dedupe input=%s unique_url=%s dropped_url=%s dropped_title=%s kept=%s",
        len(articles),
        len(by_url),
        dropped_url,
        dropped_title,
        len(kept),
    )
    return kept


def _dedupe_raw(articles: List[RawArticle]) -> List[RawArticle]:
    return dedupe_fetch_batch(articles)


def fetch_and_process_news() -> int:
    """
    Hourly ingest: pull as many unique articles as NewsAPI + Currents allow
    (everything + each top-headlines category), then tag and score locally.
    """
    pooled: List[RawArticle] = []
    pooled.extend(fetch_from_newsapi_everything())
    pooled.extend(fetch_from_newsapi_markets())
    for category in NEWSAPI_CATEGORIES:
        pooled.extend(fetch_from_newsapi(category=category))
        time.sleep(0.2)

    pooled.extend(fetch_from_currents("general"))
    raw_articles = _dedupe_raw(pooled)
    if not raw_articles:
        logger.info("live fetch empty; generating synthetic dataset")
        from app.services.synthesizer import generate_raw_synthesized_articles
        raw_articles = generate_raw_synthesized_articles(records_per_tag=100)
        if not raw_articles:
            for category in NEWSAPI_CATEGORIES:
                raw_articles.extend(generate_mock_articles(category))
            raw_articles = _dedupe_raw(raw_articles)

    logger.info("processing unique raw articles=%s", len(raw_articles))
    count = process_raw_articles(raw_articles)
    logger.info("processing complete stored=%s", count)
    return count
