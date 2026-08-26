from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

@dataclass
class RawArticle:
    title: str
    description: Optional[str]
    url: str
    source_name: Optional[str]
    api_category: Optional[str]
    image_url: Optional[str]
    published_at: Optional[str]
    url_hash: str

@dataclass
class SentimentResult:
    compound: float
    positive: float
    negative: float
    neutral: float
    label: str  # "good", "bad", "ugly", "neutral"
    ugly_keyword_count: int

# Pydantic Schemas for API responses

class ArticleSchema(BaseModel):
    id: int
    url_hash: str
    title: str
    description: Optional[str] = None
    source_name: Optional[str] = None
    api_category: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    published_at: Optional[str] = None
    fetched_at: str
    compound_score: float
    positive_score: float
    negative_score: float
    neutral_score: float
    sentiment_label: str
    tags: List[str] = []

class TagInfoSchema(BaseModel):
    tag: str
    label: str
    icon: str
    color: str
    dominant_mode: str  # "good", "bad", "ugly", "neutral"
    article_count: int

class DashboardModeSchema(BaseModel):
    selected_tags: List[str]
    dominant_mode: str
    total_articles: int
    good_count: int
    bad_count: int
    ugly_count: int
    neutral_count: int
    avg_compound: float

class TrendPointSchema(BaseModel):
    snapshot_time: str
    avg_compound: float
    good_count: int
    bad_count: int
    ugly_count: int
    neutral_count: int
    total_articles: int

class ContagionEventSchema(BaseModel):
    id: int
    detected_at: str
    source_tag: str
    target_tag: str
    severity: str
    source_compound_delta: float
    target_compound_current: float
    message: str
    resolved: bool
