from app.services.desk_chat import _extract_ids, _keyword_fallback

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
