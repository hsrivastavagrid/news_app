import logging
import re
from typing import Optional, List, Dict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from app.config import (
    UGLY_KEYWORDS,
    VADER_GOOD_THRESHOLD,
    VADER_BAD_THRESHOLD,
    VADER_UGLY_COMPOUND_WITH_KW,
    VADER_UGLY_COMPOUND_NO_KW,
    DOMAIN_TAGS,
    CONTAGION_NEIGHBORS,
)
from app.models import SentimentResult
from app.database import db

logger = logging.getLogger("newspulse.sentiment")

# Initialize VADER Analyzer once
vader = SentimentIntensityAnalyzer()

def count_ugly_keywords(text: str) -> int:
    """Counts matches of ugly keywords in text using word boundaries."""
    text_lower = text.lower()
    count = 0
    for kw in UGLY_KEYWORDS:
        # Match whole word or stem
        if re.search(r'\b' + re.escape(kw), text_lower):
            count += 1
    return count

def analyze_text(title: str, description: Optional[str] = None) -> SentimentResult:
    """Performs VADER scoring & Ugly keyword boost to classify article sentiment."""
    full_text = f"{title}. {description or ''}"
    scores = vader.polarity_scores(full_text)
    
    compound = scores["compound"]
    positive = scores["pos"]
    negative = scores["neg"]
    neutral = scores["neu"]
    
    ugly_kw_count = count_ugly_keywords(full_text)
    
    # Classification logic
    if compound <= VADER_UGLY_COMPOUND_WITH_KW and ugly_kw_count >= 1:
        label = "ugly"
    elif compound <= VADER_UGLY_COMPOUND_NO_KW:
        label = "ugly"
    elif compound <= VADER_BAD_THRESHOLD:
        label = "bad"
    elif compound >= VADER_GOOD_THRESHOLD:
        label = "good"
    else:
        label = "neutral"
        
    return SentimentResult(
        compound=round(compound, 3),
        positive=round(positive, 3),
        negative=round(negative, 3),
        neutral=round(neutral, 3),
        label=label,
        ugly_keyword_count=ugly_kw_count,
    )

def detect_cross_domain_contagion():
    """
    Checks recent tag sentiment trends across all tag-pairs.
    Emits a contagion alert if Tag A drops > 0.3 while Tag B is still stable.
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get latest avg_compound for each tag in current hour vs 3 hours ago
        tag_deltas = {}
        tag_current = {}
        
        for tag in DOMAIN_TAGS:
            cursor.execute(
                """
                SELECT avg_compound, snapshot_time
                FROM tag_snapshots
                WHERE tag = ?
                ORDER BY snapshot_time DESC
                LIMIT 4
                """,
                (tag,),
            )
            rows = cursor.fetchall()
            if len(rows) >= 2:
                latest = rows[0]["avg_compound"]
                older = rows[-1]["avg_compound"]
                tag_current[tag] = latest
                tag_deltas[tag] = latest - older  # negative means deteriorating
            elif len(rows) == 1:
                tag_current[tag] = rows[0]["avg_compound"]
                tag_deltas[tag] = 0.0

        # One alert per collapsing source → related lagging neighbors only.
        for tag_a in DOMAIN_TAGS:
            delta_a = tag_deltas.get(tag_a, 0.0)
            if delta_a > -0.3:
                continue
            lagging = [
                tag_b
                for tag_b in CONTAGION_NEIGHBORS.get(tag_a, ())
                if tag_deltas.get(tag_b, 0.0) >= -0.1
            ]
            if not lagging:
                continue
            targets = ", ".join(t.title() for t in lagging)
            msg = (
                f"Cross-Domain Contagion Alert: {tag_a.title()} sentiment dropped sharply "
                f"(Delta {round(delta_a, 2)}). Historical ripple effect predicts {targets} "
                f"may shift negative within 2-4 hours."
            )
            primary = lagging[0]
            severity = "high" if delta_a <= -0.5 else "moderate"
            logger.info("contagion alert %s -> %s severity=%s", tag_a, lagging, severity)
            db.insert_contagion_event(
                source_tag=tag_a,
                target_tag=primary,
                severity=severity,
                source_delta=round(delta_a, 3),
                target_current=round(tag_current.get(primary, 0.0), 3),
                message=msg,
            )
    except Exception:
        logger.exception("contagion detection failed")
    finally:
        conn.close()
