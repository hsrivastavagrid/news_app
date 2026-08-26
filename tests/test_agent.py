from app.services.filter_agent import heuristic_parse

def test_heuristic_skip_ugly_tech_finance():
    result = heuristic_parse("I want tech and finance news, skip ugly, keywords AI")
    assert "tech" in result.tags
    assert "finance" in result.tags
    assert "ugly" not in result.sentiments
    assert "good" in result.sentiments
    assert any(k.lower() == "ai" for k in result.keywords)
    assert result.tag_mode == "union"

def test_heuristic_only_good():
    result = heuristic_parse("only good health news")
    assert result.tags == ["health"]
    assert result.sentiments == ["good"]
