import json
import logging
import sqlite3
import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("newspulse.db")
from app.config import DB_PATH, DOMAIN_TAGS, TAG_METADATA
from app.urls import source_article_url
from app.models import (
    RawArticle,
    SentimentResult,
    ArticleSchema,
    TagInfoSchema,
    DashboardModeSchema,
    TrendPointSchema,
    ContagionEventSchema,
    PreferenceSchema,
)

def get_rolling_window() -> Tuple[str, str]:
    """
    Returns (start, end) UTC ISO strings for a rolling 1-hour window ending NOW.
    Example: if now = 15:44:00 UTC → start = 14:44:00, end = 15:44:00.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start = now_utc - datetime.timedelta(hours=1)
    return (
        start.strftime("%Y-%m-%d %H:%M:%S"),
        now_utc.strftime("%Y-%m-%d %H:%M:%S"),
    )

def get_floor_hour_window() -> Tuple[str, str]:
    """Alias for backwards compatibility."""
    return get_rolling_window()

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    schema_path = DB_PATH.parent.parent / "app" / "database" / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = get_db_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("database schema applied path=%s", DB_PATH)
        conn.commit()
    except Exception:
        logger.exception("database init failed path=%s", DB_PATH)
        raise
    finally:
        conn.close()


def purge_non_live_articles(conn: Optional[sqlite3.Connection] = None) -> int:
    """Delete mock/synth rows (fake hosts, Google-search fallbacks, demo sources)."""
    own = conn is None
    if own:
        conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM articles
            WHERE source_name IN ('NewsPulse Global Service', 'NewsPulse Syndicate')
               OR IFNULL(url, '') LIKE '%example.com%'
               OR IFNULL(url, '') LIKE '%/articles/synth-%'
               OR IFNULL(url, '') LIKE '%news.google.com/search%'
               OR IFNULL(title, '') LIKE '%(Cycle %'
            """
        )
        deleted = cursor.rowcount or 0
        if own:
            conn.commit()
        return deleted
    finally:
        if own:
            conn.close()


def insert_article(
    raw: RawArticle,
    sentiment: SentimentResult,
    tags: List[str],
    fetched_at: Optional[str] = None,
) -> Optional[int]:
    """Insert article and its multi-tags into sqlite db with SHA256 url deduplication."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Default fetched_at to current UTC string if not provided
    if not fetched_at:
        fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute(
            """
            INSERT INTO articles (
                url_hash, title, description, source_name, api_category,
                url, image_url, published_at, fetched_at, compound_score, positive_score,
                negative_score, neutral_score, sentiment_label, ugly_keyword_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_hash) DO NOTHING;
            """,
            (
                raw.url_hash,
                raw.title,
                raw.description,
                raw.source_name,
                raw.api_category,
                raw.url,
                raw.image_url,
                raw.published_at,
                fetched_at,
                sentiment.compound,
                sentiment.positive,
                sentiment.negative,
                sentiment.neutral,
                sentiment.label,
                sentiment.ugly_keyword_count,
            ),
        )
        
        article_id = cursor.lastrowid
        if not article_id:
            # Already existed
            cursor.execute("SELECT id FROM articles WHERE url_hash = ?", (raw.url_hash,))
            row = cursor.fetchone()
            article_id = row["id"] if row else None

        if article_id and tags:
            for tag in tags:
                cursor.execute(
                    """
                    INSERT INTO article_tags (article_id, tag)
                    VALUES (?, ?)
                    ON CONFLICT(article_id, tag) DO NOTHING;
                    """,
                    (article_id, tag),
                )
        conn.commit()
        return article_id
    except Exception:
        conn.rollback()
        logger.exception("insert_article failed url_hash=%s", raw.url_hash)
        raise
    finally:
        conn.close()

def get_all_tags_with_metadata(
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
) -> List[TagInfoSchema]:
    """
    Returns each domain tag with its article count and dominant sentiment mode.
    time_from / time_to are ISO datetime strings (UTC). If both provided, filters
    articles to that exact rolling window (start <= published_at <= end).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []

    if time_from and time_to:
        time_filter = "WHERE at.tag = ? AND datetime(a.published_at) >= datetime(?) AND datetime(a.published_at) <= datetime(?)"
        time_params_extra = [time_from, time_to]
    else:
        time_filter = "WHERE at.tag = ?"
        time_params_extra = []

    try:
        for tag_name in DOMAIN_TAGS:
            cursor.execute(
                f"""
                SELECT
                    a.sentiment_label,
                    COUNT(*) as count
                FROM articles a
                JOIN article_tags at ON a.id = at.article_id
                {time_filter}
                GROUP BY a.sentiment_label
                """,
                [tag_name] + time_params_extra,
            )
            rows = cursor.fetchall()
            counts = {"good": 0, "bad": 0, "ugly": 0, "neutral": 0}
            total = 0
            for r in rows:
                counts[r["sentiment_label"]] = r["count"]
                total += r["count"]

            dominant_mode = "neutral"
            if total > 0:
                dominant_mode = max(counts, key=counts.get)

            meta = TAG_METADATA.get(tag_name, {"label": tag_name.title(), "icon": "", "color": "#6B7280"})
            results.append(
                TagInfoSchema(
                    tag=tag_name,
                    label=meta["label"],
                    icon=meta.get("icon", ""),
                    color=meta["color"],
                    dominant_mode=dominant_mode,
                    article_count=total,
                )
            )
        return results
    finally:
        conn.close()

def build_intersection_query(tags: Optional[List[str]]) -> Tuple[str, List[Any]]:
    """Builds SQL WHERE / JOIN clause for multi-tag INTERSECTION (AND logic)."""
    if not tags:
        return "FROM articles a", []
    
    joins = []
    params = []
    for idx, tag in enumerate(tags):
        alias = f"at_{idx}"
        joins.append(f"JOIN article_tags {alias} ON a.id = {alias}.article_id AND {alias}.tag = ?")
        params.append(tag)
    
    query_from = f"FROM articles a {' '.join(joins)}"
    return query_from, params

def build_filter_clauses(
    tags: Optional[List[str]] = None,
    tag_mode: str = "union",
    sentiments: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
) -> Tuple[str, str, List[Any]]:
    """FROM + WHERE for personalized feed filters. Default tag_mode is UNION (any selected tag)."""
    tags_clean = [t.strip().lower() for t in tags if t and t.strip()] if tags else []
    sentiments_clean = [s.strip().lower() for s in sentiments if s and s.strip()] if sentiments else []
    keywords_clean = [k.strip() for k in keywords if k and k.strip()] if keywords else []
    mode = (tag_mode or "union").lower()
    if mode not in ("union", "intersection"):
        mode = "union"

    params: List[Any] = []
    if tags_clean and mode == "intersection":
        from_clause, params = build_intersection_query(tags_clean)
    else:
        from_clause = "FROM articles a"

    wheres: List[str] = []
    if tags_clean and mode == "union":
        placeholders = ",".join("?" * len(tags_clean))
        wheres.append(
            f"a.id IN (SELECT article_id FROM article_tags WHERE tag IN ({placeholders}))"
        )
        params.extend(tags_clean)

    if time_from and time_to:
        wheres.append(
            "datetime(a.published_at) >= datetime(?) AND datetime(a.published_at) <= datetime(?)"
        )
        params.extend([time_from, time_to])

    if sentiments_clean:
        placeholders = ",".join("?" * len(sentiments_clean))
        wheres.append(f"a.sentiment_label IN ({placeholders})")
        params.extend(sentiments_clean)

    if keywords_clean:
        kw_parts = []
        for kw in keywords_clean:
            kw_parts.append("(LOWER(a.title) LIKE ? OR LOWER(IFNULL(a.description, '')) LIKE ?)")
            like = f"%{kw.lower()}%"
            params.extend([like, like])
        wheres.append("(" + " OR ".join(kw_parts) + ")")

    where_str = f"WHERE {' AND '.join(wheres)}" if wheres else ""
    return from_clause, where_str, params

def get_dashboard_mode(
    tags: Optional[List[str]] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    tag_mode: str = "union",
    sentiments: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
) -> DashboardModeSchema:
    """
    Calculates overall sentiment mode for the personalized filter set within a rolling time window.
    Default tag_mode is union (any selected priority tag).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    tags_clean = [t.strip().lower() for t in tags if t.strip()] if tags else []
    from_clause, where_clause, params = build_filter_clauses(
        tags=tags_clean,
        tag_mode=tag_mode,
        sentiments=sentiments,
        keywords=keywords,
        time_from=time_from,
        time_to=time_to,
    )
    
    sql = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN a.sentiment_label = 'good' THEN 1 ELSE 0 END) as good_count,
            SUM(CASE WHEN a.sentiment_label = 'bad' THEN 1 ELSE 0 END) as bad_count,
            SUM(CASE WHEN a.sentiment_label = 'ugly' THEN 1 ELSE 0 END) as ugly_count,
            SUM(CASE WHEN a.sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
            AVG(a.compound_score) as avg_compound
        {from_clause}
        {where_clause}
    """
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        
        total = (row["total"] or 0) if row else 0
        good = row["good_count"] or 0 if row else 0
        bad = row["bad_count"] or 0 if row else 0
        ugly = row["ugly_count"] or 0 if row else 0
        neutral = row["neutral_count"] or 0 if row else 0
        avg_comp = round(row["avg_compound"] or 0.0, 3) if row else 0.0
        
        mode_counts = {"good": good, "bad": bad, "ugly": ugly, "neutral": neutral}
        dominant_mode = max(mode_counts, key=mode_counts.get) if total > 0 else "neutral"
        
        return DashboardModeSchema(
            selected_tags=tags_clean,
            dominant_mode=dominant_mode,
            total_articles=total,
            good_count=good,
            bad_count=bad,
            ugly_count=ugly,
            neutral_count=neutral,
            avg_compound=avg_comp,
        )
    finally:
        conn.close()

def get_trends(tags: Optional[List[str]] = None, hours: int = 24) -> List[TrendPointSchema]:
    """Retrieves hourly time-series trends for tag intersection."""
    conn = get_db_connection()
    cursor = conn.cursor()
    tags_clean = [t.strip().lower() for t in tags if t.strip()] if tags else []
    
    from_clause, params = build_intersection_query(tags_clean)
    
    sql = f"""
        SELECT 
            strftime('%Y-%m-%d %H:00:00', a.published_at) as hour_slot,
            COUNT(*) as total,
            SUM(CASE WHEN a.sentiment_label = 'good' THEN 1 ELSE 0 END) as good_count,
            SUM(CASE WHEN a.sentiment_label = 'bad' THEN 1 ELSE 0 END) as bad_count,
            SUM(CASE WHEN a.sentiment_label = 'ugly' THEN 1 ELSE 0 END) as ugly_count,
            SUM(CASE WHEN a.sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
            AVG(a.compound_score) as avg_compound
        {from_clause}
        WHERE datetime(a.published_at) >= datetime('now', '-{hours} hours')
        GROUP BY hour_slot
        ORDER BY hour_slot ASC
    """
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        points = []
        for r in rows:
            points.append(
                TrendPointSchema(
                    snapshot_time=r["hour_slot"],
                    avg_compound=round(r["avg_compound"] or 0.0, 3),
                    good_count=r["good_count"] or 0,
                    bad_count=r["bad_count"] or 0,
                    ugly_count=r["ugly_count"] or 0,
                    neutral_count=r["neutral_count"] or 0,
                    total_articles=r["total"] or 0,
                )
            )
        return points
    finally:
        conn.close()

def get_articles(
    tags: Optional[List[str]] = None,
    sentiment: Optional[str] = None,
    sentiments: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    tag_mode: str = "union",
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    limit: int = 100
) -> List[ArticleSchema]:
    """
    Personalized article feed: tag union (default) or intersection, sentiment allow-list, keyword match.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    tags_clean = [t.strip().lower() for t in tags if t.strip()] if tags else []
    sent_list = list(sentiments or [])
    if sentiment and sentiment.strip():
        sent_list.append(sentiment.strip().lower())

    from_clause, where_str, params = build_filter_clauses(
        tags=tags_clean,
        tag_mode=tag_mode,
        sentiments=sent_list,
        keywords=keywords,
        time_from=time_from,
        time_to=time_to,
    )
    
    sql = f"""
        SELECT DISTINCT
            a.id, a.url_hash, a.title, a.description, a.source_name,
            a.api_category, a.url, a.image_url, a.published_at, a.fetched_at,
            a.compound_score, a.positive_score, a.negative_score, a.neutral_score,
            a.sentiment_label
        {from_clause}
        {where_str}
        ORDER BY datetime(a.published_at) DESC
        LIMIT ?
    """
    params.append(limit)
    
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        articles = []
        for r in rows:
            art_id = r["id"]
            # Fetch tags for this article
            cursor.execute("SELECT tag FROM article_tags WHERE article_id = ?", (art_id,))
            t_rows = cursor.fetchall()
            art_tags = [tr["tag"] for tr in t_rows]
            
            articles.append(_article_from_row(r, art_tags))
        return articles
    finally:
        conn.close()


def _article_from_row(r, art_tags: List[str]) -> ArticleSchema:
    return ArticleSchema(
        id=r["id"],
        url_hash=r["url_hash"],
        title=r["title"],
        description=r["description"],
        source_name=r["source_name"],
        api_category=r["api_category"],
        url=source_article_url(r["url"]) or "",
        image_url=r["image_url"],
        published_at=r["published_at"],
        fetched_at=r["fetched_at"],
        compound_score=r["compound_score"],
        positive_score=r["positive_score"],
        negative_score=r["negative_score"],
        neutral_score=r["neutral_score"],
        sentiment_label=r["sentiment_label"],
        tags=art_tags,
    )


def get_articles_by_ids(ids: Optional[List[int]] = None) -> List[ArticleSchema]:
    """Load specific desk cards by id (order preserved)."""
    ids_clean: List[int] = []
    seen = set()
    for raw in ids or []:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n > 0 and n not in seen:
            seen.add(n)
            ids_clean.append(n)
    if not ids_clean:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        by_id = {}
        for i in range(0, len(ids_clean), 400):
            chunk = ids_clean[i : i + 400]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"""
                SELECT
                    a.id, a.url_hash, a.title, a.description, a.source_name,
                    a.api_category, a.url, a.image_url, a.published_at, a.fetched_at,
                    a.compound_score, a.positive_score, a.negative_score, a.neutral_score,
                    a.sentiment_label
                FROM articles a
                WHERE a.id IN ({placeholders})
                """,
                chunk,
            )
            for r in cursor.fetchall():
                cursor.execute("SELECT tag FROM article_tags WHERE article_id = ?", (r["id"],))
                art_tags = [tr["tag"] for tr in cursor.fetchall()]
                by_id[r["id"]] = _article_from_row(r, art_tags)
        return [by_id[i] for i in ids_clean if i in by_id]
    finally:
        conn.close()

def create_hourly_tag_snapshots():
    """Aggregates latest articles per tag and creates hourly snapshot rows."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:00:00")
    
    try:
        for tag in DOMAIN_TAGS:
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN a.sentiment_label = 'good' THEN 1 ELSE 0 END) as g_cnt,
                    SUM(CASE WHEN a.sentiment_label = 'bad' THEN 1 ELSE 0 END) as b_cnt,
                    SUM(CASE WHEN a.sentiment_label = 'ugly' THEN 1 ELSE 0 END) as u_cnt,
                    SUM(CASE WHEN a.sentiment_label = 'neutral' THEN 1 ELSE 0 END) as n_cnt,
                    AVG(a.compound_score) as avg_comp
                FROM articles a
                JOIN article_tags at ON a.id = at.article_id
                WHERE at.tag = ?
                """,
                (tag,),
            )
            r = cursor.fetchone()
            if r and r["total"] > 0:
                cursor.execute(
                    """
                    INSERT INTO tag_snapshots (
                        snapshot_time, tag, total_articles, good_count, bad_count,
                        ugly_count, neutral_count, avg_compound
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_time, tag) DO UPDATE SET
                        total_articles = excluded.total_articles,
                        good_count = excluded.good_count,
                        bad_count = excluded.bad_count,
                        ugly_count = excluded.ugly_count,
                        neutral_count = excluded.neutral_count,
                        avg_compound = excluded.avg_compound;
                    """,
                    (
                        now_str,
                        tag,
                        r["total"],
                        r["g_cnt"] or 0,
                        r["b_cnt"] or 0,
                        r["u_cnt"] or 0,
                        r["n_cnt"] or 0,
                        round(r["avg_comp"] or 0.0, 3),
                    ),
                )
        conn.commit()
    finally:
        conn.close()

def get_preferences() -> PreferenceSchema:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT tags, sentiments, keywords, tag_mode, updated_at FROM user_preferences WHERE id = 1"
        )
        row = cursor.fetchone()
        if not row:
            return PreferenceSchema()
        return PreferenceSchema(
            tags=json.loads(row["tags"] or "[]"),
            sentiments=json.loads(row["sentiments"] or "[]"),
            keywords=json.loads(row["keywords"] or "[]"),
            tag_mode=row["tag_mode"] or "union",
            updated_at=row["updated_at"],
        )
    finally:
        conn.close()

def save_preferences(prefs: PreferenceSchema) -> PreferenceSchema:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            """
            INSERT INTO user_preferences (id, tags, sentiments, keywords, tag_mode, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                tags = excluded.tags,
                sentiments = excluded.sentiments,
                keywords = excluded.keywords,
                tag_mode = excluded.tag_mode,
                updated_at = excluded.updated_at;
            """,
            (
                json.dumps(prefs.tags or []),
                json.dumps(prefs.sentiments or ["good", "bad", "ugly", "neutral"]),
                json.dumps(prefs.keywords or []),
                prefs.tag_mode or "union",
                now_str,
            ),
        )
        conn.commit()
        logger.info("preferences saved tag_mode=%s tags=%s", prefs.tag_mode, prefs.tags)
        return get_preferences()
    except Exception:
        logger.exception("save_preferences failed")
        raise
    finally:
        conn.close()

def insert_contagion_event(
    source_tag: str,
    target_tag: str,
    severity: str,
    source_delta: float,
    target_current: float,
    message: str
):
    """Log a detected cross-domain sentiment contagion event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id FROM contagion_events
            WHERE resolved = 0
              AND source_tag = ?
              AND detected_at >= datetime('now', '-6 hours')
            LIMIT 1
            """,
            (source_tag,),
        )
        if cursor.fetchone():
            logger.info("contagion skip duplicate source=%s", source_tag)
            return
        cursor.execute(
            """
            INSERT INTO contagion_events (
                source_tag, target_tag, severity, source_compound_delta,
                target_compound_current, message
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (source_tag, target_tag, severity, source_delta, target_current, message),
        )
        conn.commit()
    finally:
        conn.close()

def get_active_contagion_alerts() -> List[ContagionEventSchema]:
    """Returns active (unresolved) contagion alerts from last 12 hours."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, detected_at, source_tag, target_tag, severity,
                   source_compound_delta, target_compound_current, message, resolved
            FROM contagion_events
            WHERE id IN (
                SELECT MAX(id)
                FROM contagion_events
                WHERE resolved = 0
                  AND detected_at >= datetime('now', '-12 hours')
                GROUP BY source_tag
            )
            ORDER BY source_compound_delta ASC, detected_at DESC
            LIMIT 6
            """
        )
        rows = cursor.fetchall()
        events = []
        for r in rows:
            events.append(
                ContagionEventSchema(
                    id=r["id"],
                    detected_at=r["detected_at"],
                    source_tag=r["source_tag"],
                    target_tag=r["target_tag"],
                    severity=r["severity"],
                    source_compound_delta=r["source_compound_delta"],
                    target_compound_current=r["target_compound_current"],
                    message=r["message"],
                    resolved=bool(r["resolved"]),
                )
            )
        return events
    finally:
        conn.close()
