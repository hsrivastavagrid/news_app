import hashlib
import time
import re
import datetime
from typing import List, Optional
import httpx

from app.config import (
    NEWSAPI_KEY,
    CURRENTS_API_KEY,
    NEWSAPI_BASE_URL,
    CURRENTS_BASE_URL,
    CATEGORY_TO_TAG,
    TAG_KEYWORDS,
    DOMAIN_TAGS,
)
from app.models import RawArticle
from app.services.sentiment_analyzer import analyze_text, detect_cross_domain_contagion
from app.database import db

def compute_url_hash(url: str) -> str:
    """Computes SHA256 hash of URL for deduplication."""
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()

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

def fetch_from_newsapi(category: str) -> List[RawArticle]:
    """Fetches top headlines from NewsAPI.org for the most recent complete hour window.
    
    If now = 14:55 UTC, fetches from 13:00 UTC to 14:00 UTC.
    """
    if not NEWSAPI_KEY:
        return []

    # Compute floor-hour window: previous complete hour based on floor(now)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    floor_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    window_start = floor_hour - datetime.timedelta(hours=1)
    window_start_iso = window_start.isoformat()

    params = {
        "category": category,
        "language": "en",
        "pageSize": 20,
        "apiKey": NEWSAPI_KEY,
        "from": window_start_iso,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(NEWSAPI_BASE_URL, params=params)
            if resp.status_code == 426:
                print(f"[NewsAPI] 426 Upgrade Required for category {category} — free tier may be limited to localhost")
                return []
            if resp.status_code == 429:
                print(f"[NewsAPI] Rate limited (429) for category {category}")
                return []
            if resp.status_code != 200:
                print(f"[NewsAPI] Error {resp.status_code} for category {category}: {resp.text[:200]}")
                return []
            data = resp.json()
            if data.get("status") != "ok":
                print(f"[NewsAPI] Non-OK status for category {category}: {data.get('message', '')}")
                return []

            articles = []
            for item in data.get("articles", []):
                art_url = item.get("url")
                title = item.get("title") or ""
                # NewsAPI sometimes returns "[Removed]" placeholder articles
                if not art_url or title == "[Removed]":
                    continue
                articles.append(
                    RawArticle(
                        title=title,
                        description=item.get("description"),
                        url=art_url,
                        source_name=(item.get("source") or {}).get("name"),
                        api_category=NEWSAPI_CATEGORY_MAP.get(category, category),
                        image_url=item.get("urlToImage"),
                        published_at=item.get("publishedAt") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        url_hash=compute_url_hash(art_url),
                    )
                )
            print(f"[NewsAPI] Fetched {len(articles)} articles for category '{category}' (last hour)")
            return articles
    except Exception as e:
        print(f"[NewsAPI] Fetch exception for category {category}: {e}")
        return []

def fetch_from_currents(category: str) -> List[RawArticle]:
    """Fallback fetch from Currents API."""
    if not CURRENTS_API_KEY:
        return []

    url = f"{CURRENTS_BASE_URL}?language=en&apiKey={CURRENTS_API_KEY}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
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
            return articles
    except Exception as e:
        print(f"[Currents] Fetch exception: {e}")
        return []

def generate_mock_articles(category: str) -> List[RawArticle]:
    """Generates dynamic realistic articles when API keys are not provided or rate-limited.
    
    Uses a timestamp within the most recent complete floor-hour window so mock
    articles appear correctly in floor-hour filtered queries.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    floor_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    # Place mock articles 30 minutes into the previous complete hour window
    mock_time = floor_hour - datetime.timedelta(minutes=30)
    mock_iso = mock_time.isoformat()
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

def fetch_and_process_news() -> int:
    """
    Main job pipeline:
    1. Fetches news for categories from NewsAPI.org -> Currents -> Mock fallback
    2. Computes VADER sentiment & ugly keywords
    3. Assigns multi-tags per article
    4. Inserts into SQLite database with URL dedup
    5. Computes hourly tag snapshots
    6. Triggers contagion detection
    """
    total_new_articles = 0

    for category in NEWSAPI_CATEGORIES:
        raw_articles = fetch_from_newsapi(category)
        if not raw_articles:
            raw_articles = fetch_from_currents(category)
        if not raw_articles:
            raw_articles = generate_mock_articles(category)

        for raw in raw_articles:
            # 1. Analyze sentiment
            sentiment = analyze_text(raw.title, raw.description)

            # 2. Assign domain tags
            tags = assign_tags(raw.api_category, raw.title, raw.description)

            # 3. Store in DB
            article_id = db.insert_article(raw, sentiment, tags)
            if article_id:
                total_new_articles += 1

    # 4. Generate hourly snapshots
    db.create_hourly_tag_snapshots()

    # 5. Run contagion detection
    detect_cross_domain_contagion()

    return total_new_articles
