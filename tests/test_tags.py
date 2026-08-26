import pytest
from app.services.news_fetcher import assign_tags
from app.database.db import build_intersection_query

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
