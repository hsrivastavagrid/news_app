import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# API Keys
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# This Groq account does not serve llama-3.1-8b-instant. qwen/qwen3.8-27b is
# available and has a 1000 req window (allam-2-7b has 7000 if you need volume).
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# Server Settings
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", 60))
FETCH_ON_START = os.getenv("FETCH_ON_START", "true").lower() in ("1", "true", "yes")
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "newspulse.log"))

# Database
DB_PATH = BASE_DIR / "data" / "news_pulse.db"

# API Endpoints
NEWSAPI_BASE_URL = "https://newsapi.org/v2/top-headlines"
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
CURRENTS_BASE_URL = "https://api.currentsapi.services/v1/latest-news"

# All supported domain tags
DOMAIN_TAGS = [
    "politics",
    "finance",
    "tech",
    "health",
    "sports",
    "science",
    "entertainment",
    "world",
]

# Only emit contagion along historically related domains (not a full cartesian product).
CONTAGION_NEIGHBORS = {
    "politics": ("finance", "world"),
    "finance": ("politics", "tech", "world"),
    "tech": ("finance", "science"),
    "health": ("science", "world"),
    "sports": ("entertainment",),
    "science": ("tech", "health", "world"),
    "entertainment": ("sports",),
    "world": ("politics", "finance", "health"),
}

# Tag display names and accents (No emojis)
TAG_METADATA = {
    "politics": {"label": "Politics", "icon": "", "color": "#F59E0B"},
    "finance": {"label": "Finance", "icon": "", "color": "#06B6D4"},
    "tech": {"label": "Technology", "icon": "", "color": "#8B5CF6"},
    "health": {"label": "Health", "icon": "", "color": "#EC4899"},
    "sports": {"label": "Sports", "icon": "", "color": "#22C55E"},
    "science": {"label": "Science", "icon": "", "color": "#14B8A6"},
    "entertainment": {"label": "Entertainment", "icon": "", "color": "#F97316"},
    "world": {"label": "World News", "icon": "", "color": "#3B82F6"},
    "general": {"label": "General", "icon": "", "color": "#6B7280"},
}

# Category to Tag Base Mapping
CATEGORY_TO_TAG = {
    "general": None,
    "world": "world",
    "nation": "politics",
    "business": "finance",
    "technology": "tech",
    "entertainment": "entertainment",
    "sports": "sports",
    "science": "science",
    "health": "health",
}

# Domain Tag Keywords for Multi-Tag Routing
TAG_KEYWORDS = {
    "politics": {
        "election", "president", "congress", "senate", "parliament", "minister",
        "legislation", "sanctions", "diplomacy", "geopolitical", "referendum",
        "campaign", "bipartisan", "democrat", "republican", "policy", "governor",
        "supreme court", "impeachment", "treaty", "tariff", "regulation",
        "government", "vote", "opposition", "coalition", "mandate", "politics", "political"
    },
    "finance": {
        "stock", "market", "shares", "investor", "gdp", "inflation", "fed",
        "interest rate", "earnings", "revenue", "ipo", "nasdaq", "dow jones",
        "wall street", "hedge fund", "cryptocurrency", "bitcoin", "bond",
        "recession", "bailout", "dividend", "merger", "acquisition", "forex",
        "banking", "economy", "fiscal", "monetary", "finance", "financial"
    },
    "tech": {
        "ai", "artificial intelligence", "startup", "software", "hardware",
        "silicon valley", "cybersecurity", "data breach", "cloud", "saas",
        "blockchain", "robotics", "quantum", "semiconductor", "chip",
        "apple", "google", "microsoft", "meta", "tesla", "openai", "nvidia", "tech", "technology"
    },
    "health": {
        "vaccine", "pandemic", "hospital", "disease", "treatment", "drug",
        "clinical trial", "fda", "cancer", "mental health", "virus",
        "outbreak", "surgery", "pharma", "diagnosis", "therapy", "who", "health", "medical"
    },
    "sports": {
        "championship", "tournament", "league", "nba", "nfl", "fifa",
        "olympics", "premier league", "cricket", "tennis", "formula 1",
        "athlete", "coach", "playoff", "stadium", "match", "score", "sports", "football"
    },
    "science": {
        "nasa", "space", "climate", "research", "discovery", "experiment",
        "physicist", "biology", "genome", "fossil", "asteroid", "mars",
        "evolution", "species", "emission", "renewable", "carbon", "science", "scientific"
    },
    "entertainment": {
        "movie", "film", "box office", "netflix", "celebrity", "album",
        "concert", "grammy", "oscar", "emmy", "streaming", "tv show",
        "actor", "singer", "director", "premiere", "trailer", "entertainment", "music"
    },
    "world": {
        "united nations", "nato", "eu", "refugee", "humanitarian", "war",
        "conflict", "ceasefire", "peacekeeping", "border", "migration",
        "embassy", "summit", "bilateral", "foreign affairs", "g7", "g20", "global", "international"
    }
}

# "Ugly" Sentiment Keywords (scandalous, disturbing, tragic, outrageous)
UGLY_KEYWORDS = {
    "scandal", "corruption", "massacre", "fraud", "abuse", "murder",
    "assault", "trafficking", "genocide", "torture", "rape", "terrorist",
    "bombing", "shooting", "crash", "catastrophe", "explosion", "scam",
    "embezzlement", "coverup", "crisis", "outrage", "horrific", "gruesome",
    "atrocity", "devastating", "predator", "exploitation", "collapse",
    "tragedy", "fatal", "disaster", "bribery", "hostage"
}

# VADER Score Classification Thresholds
VADER_GOOD_THRESHOLD = 0.05
VADER_BAD_THRESHOLD = -0.05
VADER_UGLY_COMPOUND_WITH_KW = -0.3
VADER_UGLY_COMPOUND_NO_KW = -0.5
