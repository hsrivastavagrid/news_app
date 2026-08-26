import pytest
from app.services.sentiment_analyzer import analyze_text, count_ugly_keywords

def test_sentiment_good_classification():
    result = analyze_text("Breakthrough Cancer Treatment Approved", "FDA approves highly effective new therapy with great success.")
    assert result.label == "good"
    assert result.compound >= 0.05

def test_sentiment_bad_classification():
    result = analyze_text("Economic Growth Slows Down Sharply", "Quarterly GDP reports indicate weak consumer spending and declining revenues.")
    assert result.label == "bad"
    assert result.compound <= -0.05

def test_sentiment_ugly_classification():
    result = analyze_text("Minister Arrested in Massive Bribery and Fraud Scandal", "Police uncover horrific corruption and embezzlement network within government.")
    assert result.label == "ugly"
    assert result.ugly_keyword_count >= 1

def test_ugly_keyword_counter():
    count = count_ugly_keywords("Massive scandal and corruption exposed in illegal fraud scheme.")
    assert count == 3
