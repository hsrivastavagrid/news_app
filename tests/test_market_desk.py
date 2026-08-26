from app.models import ArticleSchema
from app.services.market_desk import (
    analyze_story,
    build_tape,
    classify_event,
    decorate_article,
    extract_companies,
)


def test_extract_apple_earnings_and_skip_pie():
    hits = extract_companies("Apple shares slump after earnings miss", "Investors dump AAPL following a revenue miss.")
    tickers = {c.ticker for c in hits}
    assert "AAPL" in tickers
    assert extract_companies("Best apple pie recipe for fall") == []


def test_extract_nvidia_and_dollar_ticker():
    hits = extract_companies("NVIDIA beats estimates as $MSFT lifts cloud capex")
    tickers = {c.ticker for c in hits}
    assert "NVDA" in tickers
    assert "MSFT" in tickers


def test_extract_skips_meta_analysis():
    assert extract_companies("A meta-analysis of climate policy outcomes") == []
    hits = extract_companies("Meta Platforms faces FTC antitrust probe")
    assert any(c.ticker == "META" for c in hits)


def test_fed_rates_event():
    event, label = classify_event("Federal Reserve signals another rate hike", "Powell says inflation remains sticky.")
    assert event == "rates"
    brief = analyze_story(
        "Federal Reserve signals another rate hike",
        "Powell says inflation remains sticky.",
        "bad",
    )
    assert any(c.ticker == "FOMC" for c in brief.companies)
    assert brief.signal == "risk_off"


def test_bankruptcy_is_risk_off():
    brief = analyze_story("Boeing suppliers face bankruptcy after delivery halt", None, "ugly")
    assert any(c.ticker == "BA" for c in brief.companies)
    assert brief.event_type == "bankruptcy"
    assert brief.signal == "risk_off"


def test_earnings_beat_is_risk_on():
    brief = analyze_story("NVIDIA beats estimates and raises guidance", "Data-center revenue hits a record high.", "good")
    assert brief.event_type == "earnings"
    assert brief.signal == "risk_on"
    assert "NVDA" in {c.ticker for c in brief.companies}


def _article(**kwargs):
    base = dict(
        id=1,
        url_hash="abc",
        title="NVIDIA beats estimates and raises guidance",
        description="Record data-center revenue.",
        source_name="Reuters",
        url="https://www.reuters.com/nvda-1",
        fetched_at="2026-08-27 12:00:00",
        compound_score=0.6,
        positive_score=0.7,
        negative_score=0.1,
        neutral_score=0.2,
        sentiment_label="good",
        tags=["finance", "tech"],
    )
    base.update(kwargs)
    return decorate_article(ArticleSchema(**base))


def test_tape_groups_risk_off_first():
    arts = [
        _article(),
        _article(
            id=2,
            url_hash="def",
            title="Boeing supplier files for bankruptcy",
            description="Chapter 11 after delivery halt.",
            compound_score=-0.8,
            sentiment_label="ugly",
        ),
        _article(
            id=3,
            url_hash="ghi",
            title="Championship match goes to overtime",
            description="A thrilling final.",
            compound_score=0.1,
            sentiment_label="neutral",
            tags=["sports"],
        ),
    ]
    tape = build_tape(arts)
    tickers = [n.ticker for n in tape.names]
    assert "BA" in tickers
    assert "NVDA" in tickers
    assert tape.risk_off_count >= 1
    assert tape.names[0].signal == "risk_off"
    assert "buy/sell" in tape.disclaimer.lower() or "not a" in tape.disclaimer.lower()
