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

class CompanyMention(BaseModel):
    ticker: str
    name: str
    sector: str


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
    companies: List[CompanyMention] = []
    event_type: str = "general"
    event_label: str = "General"
    signal: str = "watch"
    thesis: str = ""


class TapeNameSchema(BaseModel):
    ticker: str
    name: str
    sector: str
    signal: str
    event_types: List[str] = []
    article_count: int = 0
    avg_compound: float = 0.0
    headlines: List[str] = []
    thesis: str = ""


class TapeSchema(BaseModel):
    names: List[TapeNameSchema] = []
    risk_off_count: int = 0
    risk_on_count: int = 0
    watch_count: int = 0
    name_count: int = 0
    disclaimer: str = ""

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
    window_from: Optional[str] = None
    window_to: Optional[str] = None

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

class PreferenceSchema(BaseModel):
    tags: List[str] = []
    sentiments: List[str] = ["good", "bad", "ugly", "neutral"]
    keywords: List[str] = []
    tag_mode: str = "union"
    updated_at: Optional[str] = None

class AgentFilterRequest(BaseModel):
    message: str
    persist: bool = True

class AgentFilterResponse(BaseModel):
    tags: List[str] = []
    sentiments: List[str] = []
    keywords: List[str] = []
    tag_mode: str = "union"
    explanation: str = ""
    persisted: bool = False

class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatTurn] = []
    tags: List[str] = []
    sentiments: List[str] = []
    keywords: List[str] = []
    tag_mode: str = "union"
    article_ids: List[int] = []

class ChatCitation(BaseModel):
    id: int
    title: str
    source_name: str = ""
    url: str = ""
    sentiment_label: str = "neutral"
    tags: List[str] = []

class ChatResponse(BaseModel):
    answer: str
    citations: List[ChatCitation] = []
    desk_count: int = 0
