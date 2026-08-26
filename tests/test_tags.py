import pytest
from app.services.news_fetcher import assign_tags
from app.database.db import build_intersection_query, build_filter_clauses

def test_assign_tags_multi_category():
    # Political + Financial news
    tags = assign_tags("business", "Congress Passes New Financial Regulation Policy Bill", "Lawmakers approve banking inflation control measures in senate vote.")
    assert "politics" in tags
    assert "finance" in tags

def test_assign_tags_fallback():
    tags = assign_tags("general", "Random Event Occurred Yesterday", "Nothing specific was reported.")
    assert tags == ["general"]

def test_build_intersection_query_empty():
    sql, params = build_intersection_query([])
    assert "FROM articles a" in sql
    assert len(params) == 0

def test_build_intersection_query_multi_tags():
    sql, params = build_intersection_query(["politics", "finance"])
    assert "JOIN article_tags at_0" in sql
    assert "JOIN article_tags at_1" in sql
    assert params == ["politics", "finance"]

def test_build_filter_union_with_sentiment_and_keywords():
    from_clause, where_sql, params = build_filter_clauses(
        tags=["tech", "finance"],
        tag_mode="union",
        sentiments=["good", "bad"],
        keywords=["AI"],
        time_from="2026-08-26 10:00:00",
        time_to="2026-08-26 11:00:00",
    )
    assert from_clause == "FROM articles a"
    assert "tag IN" in where_sql
    assert "sentiment_label IN" in where_sql
    assert "LIKE" in where_sql
    assert "tech" in params and "finance" in params
    assert "good" in params and "bad" in params
