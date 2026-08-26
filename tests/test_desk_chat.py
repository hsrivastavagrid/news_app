from app.services.desk_chat import (
    _extract_ids,
    _heuristic_select,
    _keyword_fallback,
    _read_pack,
    _score_item,
    _title_index,
)


def test_extract_ids_from_answer_and_list():
    ids = _extract_ids("World mood is ugly [2] and finance is bad [9] [1].", [1, 99], n=5)
    assert ids == [2, 1]


def test_keyword_fallback_cites_matching_story():
    corpus = [
        {
            "id": 1,
            "title": "Senate passes climate bill",
            "source_name": "Reuters",
            "url": "https://reuters.example/x",
            "sentiment_label": "good",
            "tags": ["politics"],
            "description": "Lawmakers approve climate legislation.",
        },
        {
            "id": 2,
            "title": "Championship match goes to overtime",
            "source_name": "ESPN",
            "url": "",
            "sentiment_label": "neutral",
            "tags": ["sports"],
            "description": "A thrilling final.",
        },
    ]
    answer, ids = _keyword_fallback("What happened with the climate senate bill?", corpus)
    assert 1 in ids
    assert "[1]" in answer


def _story(i, title=None, **kwargs):
    row = {
        "id": i,
        "title": title or f"Story {i}",
        "source_name": "Wire",
        "url": "",
        "sentiment_label": "neutral",
        "tags": ["world"],
        "description": f"SECRET_BODY_{i} " * 20,
        "tickers": [],
        "companies": [],
        "event_type": "general",
        "signal": "watch",
        "thesis": "",
    }
    row.update(kwargs)
    return row


def test_title_index_lists_headlines_without_bodies():
    corpus = [_story(i) for i in range(1, 61)]
    index = _title_index(corpus)
    assert "TITLE INDEX (60 headlines)" in index
    assert "[60] Story 60" in index
    assert "[1] Story 1" in index
    assert "SECRET_BODY" not in index


def test_read_pack_only_includes_opened_stories():
    corpus = [_story(1), _story(2), _story(3)]
    pack = _read_pack(corpus, [2])
    assert "Story 2" in pack
    assert "SECRET_BODY_2" in pack
    assert "SECRET_BODY_1" not in pack
    assert "Story 3" not in pack


def test_heuristic_select_opens_related_titles():
    corpus = [
        _story(1, title="Senate passes climate bill", tags=["politics"]),
        _story(2, title="Championship match goes to overtime", tags=["sports"]),
        _story(3, title="NVIDIA earnings miss hits chip stocks", tickers=["NVDA"], event_type="earnings"),
    ]
    ids = _heuristic_select("What is hitting NVIDIA earnings?", corpus, k=2)
    assert 3 in ids
    assert 2 not in ids[:1]


def test_score_item_prefers_matching_headline():
    climate = {
        "title": "Senate passes climate bill",
        "description": "Lawmakers approve climate legislation.",
        "tags": ["politics"],
        "tickers": [],
        "companies": [],
        "event_type": "general",
        "signal": "watch",
    }
    sports = {
        "title": "Championship match goes to overtime",
        "description": "A thrilling final.",
        "tags": ["sports"],
        "tickers": [],
        "companies": [],
        "event_type": "general",
        "signal": "watch",
    }
    q = "climate senate bill"
    assert _score_item(q, climate) > _score_item(q, sports)
