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
)
from app.models import SentimentResult
from app.database import db

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

        # Check pairs for contagion signal
        for tag_a in DOMAIN_TAGS:
            for tag_b in DOMAIN_TAGS:
                if tag_a == tag_b:
                    continue
                
                delta_a = tag_deltas.get(tag_a, 0.0)
                curr_b = tag_current.get(tag_b, 0.0)
                delta_b = tag_deltas.get(tag_b, 0.0)

                # Signal: Tag A collapsed (delta <= -0.3) while Tag B is lagging (delta_b >= -0.1)
                if delta_a <= -0.3 and delta_b >= -0.1:
                    msg = (
                        f"Cross-Domain Contagion Alert: {tag_a.title()} sentiment dropped sharply "
                        f"(Delta {round(delta_a, 2)}). Historical ripple effect predicts {tag_b.title()} "
                        f"may shift negative within 2-4 hours."
                    )
                    db.insert_contagion_event(
                        source_tag=tag_a,
                        target_tag=tag_b,
                        severity="high" if delta_a <= -0.5 else "moderate",
                        source_delta=round(delta_a, 3),
                        target_current=round(curr_b, 3),
                        message=msg,
                    )
    except Exception as e:
        print(f"Error during contagion detection: {e}")
    finally:
        conn.close()
