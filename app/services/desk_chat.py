"""Desk chat agent: title index → pick related headlines → read those stories."""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import (
    CHAT_ARTICLE_LIMIT,
    CHAT_MAX_OUTPUT_TOKENS,
    CHAT_READ_LIMIT,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
)
from app.database import db
from app.urls import source_article_url

logger = logging.getLogger("newspulse.chat")

SELECT_SYSTEM = """You are a news-desk librarian. You only choose which headlines to open.
Given TITLE INDEX and a question, return JSON: {"read":[1,4,9]}
Rules:
- read is 1-8 integer ids from the index that best answer the question.
- Prefer tickers, companies, and events named in the question.
- For mood/summary questions pick a diverse mix (risk-off, earnings, rates, ugly).
- Never invent ids. If unsure, pick the closest titles.
"""

ANSWER_SYSTEM = """You are the NewsPulse markets-desk correspondent.
You already chose headlines from the live desk. Answer ONLY from READ STORIES.
Rules:
1. Every factual sentence must cite [n] using the story numbers.
2. Never invent headlines, tickers, prices, or URLs.
3. If READ STORIES do not contain the answer, say so and cite the closest ones.
4. Headline risk only — not buy/sell advice.
5. 2-5 short paragraphs. Return JSON only:
{"answer":"markdown with [n] citations","citation_ids":[1,4]}
"""

_STOP = {
    "the", "and", "what", "who", "how", "why", "this", "hour", "news", "about",
    "tell", "from", "with", "which", "desk", "tape", "story", "stories", "please",
    "summarize", "summary", "related",
}


def _build_corpus(articles) -> List[Dict[str, Any]]:
    corpus = []
    for idx, art in enumerate(articles, start=1):
        url = source_article_url(art.url) or ""
        companies = [f"{c.ticker}:{c.name}" for c in (getattr(art, "companies", None) or [])]
        corpus.append(
            {
                "id": idx,
                "title": art.title,
                "source_name": art.source_name or "Wire",
                "url": url,
                "sentiment_label": art.sentiment_label,
                "tags": art.tags or [],
                "description": (art.description or "")[:400],
                "compound_score": art.compound_score,
                "tickers": [c.ticker for c in (getattr(art, "companies", None) or [])],
                "companies": companies,
                "event_type": getattr(art, "event_type", "general") or "general",
                "signal": getattr(art, "signal", "watch") or "watch",
                "thesis": getattr(art, "thesis", "") or "",
            }
        )
    return corpus


def _desk_snapshot(dashboard, tags_meta, alerts) -> str:
    lines = []
    if dashboard:
        lines.append(
            "DASHBOARD: mode={mode} total={total} good={g} bad={b} ugly={u} "
            "neutral={n} avg_compound={c} window={wf}..{wt}".format(
                mode=dashboard.dominant_mode,
                total=dashboard.total_articles,
                g=dashboard.good_count,
                b=dashboard.bad_count,
                u=dashboard.ugly_count,
                n=dashboard.neutral_count,
                c=dashboard.avg_compound,
                wf=dashboard.window_from,
                wt=dashboard.window_to,
            )
        )
    if tags_meta:
        bits = [f"{t.tag}:{t.dominant_mode}({t.article_count})" for t in tags_meta[:8]]
        lines.append("TAG MODES: " + "; ".join(bits))
    if alerts:
        lines.append("CONTAGION: " + " | ".join(a.message for a in alerts[:3]))
    return "\n".join(lines) or "DASHBOARD: empty"


def _tape_snapshot(tape) -> str:
    if not tape or not getattr(tape, "names", None):
        return "TAPE: no named issuers this hour."
    bits = [
        f"{n.ticker}:{n.signal}:{n.article_count}"
        for n in tape.names[:10]
    ]
    return (
        f"TAPE: n={tape.name_count} off={tape.risk_off_count} "
        f"on={tape.risk_on_count} | " + "; ".join(bits)
    )


def _score_item(question: str, item: Dict[str, Any]) -> int:
    tokens = [
        t
        for t in re.findall(r"[a-z0-9]{2,}", (question or "").lower())
        if t not in _STOP
    ]
    blob = (
        f"{item['title']} {' '.join(item.get('tags') or [])} "
        f"{' '.join(item.get('tickers') or [])} {' '.join(item.get('companies') or [])} "
        f"{item.get('event_type') or ''} {item.get('signal') or ''}"
    ).lower()
    return sum(1 for t in tokens if t in blob)


def _title_line(item: Dict[str, Any]) -> str:
    tickers = ",".join(item.get("tickers") or []) or "-"
    return (
        f"[{item['id']}] {item['title']} | {tickers} | "
        f"{item.get('event_type') or 'general'} | {item.get('signal') or 'watch'} | "
        f"{item.get('sentiment_label')}"
    )


def _title_index(corpus: List[Dict[str, Any]]) -> str:
    """Compact roster of every desk headline (no article body)."""
    if not corpus:
        return "TITLE INDEX: empty"
    lines = [_title_line(item) for item in corpus]
    return f"TITLE INDEX ({len(corpus)} headlines):\n" + "\n".join(lines)


def _articles_block(corpus: List[Dict[str, Any]], full_ids: Optional[set] = None) -> str:
    """Backward-compatible: title index, plus bodies only for full_ids."""
    index = _title_index(corpus)
    if not full_ids:
        return index
    return index + "\n\n" + _read_pack(corpus, sorted(full_ids))


def _read_pack(corpus: List[Dict[str, Any]], ids: Sequence[int]) -> str:
    by_id = {c["id"]: c for c in corpus}
    rows = []
    for i in ids:
        item = by_id.get(i)
        if not item:
            continue
        desc = (item.get("description") or "")[:320]
        thesis = (item.get("thesis") or "")[:160]
        rows.append(
            f"[{item['id']}] {item['title']} | {item['source_name']} | "
            f"{item['sentiment_label']} | url={item['url'] or '(none)'}\n"
            f"    {desc}" + (f"\n    {thesis}" if thesis else "")
        )
    return "READ STORIES:\n" + "\n".join(rows) if rows else "READ STORIES: none"


def _extract_ids(text: str, citation_ids: List[int], n: int) -> List[int]:
    found = [int(x) for x in re.findall(r"\[(\d+)\]", text or "")]
    merged = []
    for i in found + list(citation_ids or []):
        if 1 <= i <= n and i not in merged:
            merged.append(i)
    return merged


def _heuristic_select(question: str, corpus: List[Dict[str, Any]], k: int) -> List[int]:
    if not corpus:
        return []
    scored = [(_score_item(question, item), item["id"]) for item in corpus]
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [i for hits, i in scored if hits > 0][:k]
    if len(picked) < min(3, k):
        for item in corpus:
            if item["id"] not in picked:
                picked.append(item["id"])
            if len(picked) >= k:
                break
    return picked[:k]


def _keyword_fallback(question: str, corpus: List[Dict[str, Any]]) -> Tuple[str, List[int]]:
    ids = _heuristic_select(question, corpus, 5)
    picked = [c for c in corpus if c["id"] in ids]
    if not picked:
        return (
            "This hour's desk has no matching stories I can cite. Fetch news or widen filters.",
            [],
        )
    lines = [
        f"- {item['title']} ({item['source_name']}, {item['sentiment_label']}) [{item['id']}]"
        for item in picked
    ]
    answer = (
        "I could not reach the language model, so here are related headlines from the live desk:\n"
        + "\n".join(lines)
    )
    return answer, [item["id"] for item in picked]


def _groq_json(messages: List[Dict[str, str]], max_tokens: int) -> Optional[Dict[str, Any]]:
    if not GROQ_API_KEY:
        logger.info("chat groq skipped: no key")
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        chars = sum(len(m.get("content") or "") for m in messages)
        logger.info("chat groq request model=%s max_tokens=%s chars=%s", GROQ_MODEL, max_tokens, chars)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.1,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        err = str(exc)
        logger.exception("chat groq failed")
        if "rate_limit" in err or "Request too large" in err or "TPM" in err:
            return None
    return None


def _select_related(question: str, corpus: List[Dict[str, Any]], k: int) -> List[int]:
    """Agent step 1: from titles only, decide which stories to open."""
    fallback = _heuristic_select(question, corpus, k)
    # Groq TPM is 8k — send a ranked title slice, never full bodies.
    ranked = sorted(corpus, key=lambda c: (-_score_item(question, c), c["id"]))
    index = _title_index(ranked[:120])
    parsed = _groq_json(
        [
            {"role": "system", "content": SELECT_SYSTEM},
            {
                "role": "user",
                "content": f"{index}\n\nQUESTION: {question}\nReturn up to {k} ids.",
            },
        ],
        max_tokens=120,
    )
    if not parsed:
        logger.info("chat select heuristic ids=%s", fallback)
        return fallback
    raw = parsed.get("read") or parsed.get("citation_ids") or []
    ids = []
    try:
        for x in raw:
            i = int(x)
            if 1 <= i <= len(corpus) and i not in ids:
                ids.append(i)
    except (TypeError, ValueError):
        ids = []
    if not ids:
        return fallback
    logger.info("chat select groq ids=%s", ids[:k])
    return ids[:k]


def _answer_from_reads(
    question: str,
    history: List[Dict[str, str]],
    snapshot: str,
    corpus: List[Dict[str, Any]],
    read_ids: List[int],
) -> Optional[Dict[str, Any]]:
    """Agent step 2: read selected stories and answer."""
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{snapshot}\n\n{_read_pack(corpus, read_ids)}\n\n"
                f"Opened ids: {read_ids}. Cite only these numbers."
            ),
        },
    ]
    for turn in history[-2:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:500]})
    messages.append({"role": "user", "content": question[:800]})
    return _groq_json(messages, max_tokens=CHAT_MAX_OUTPUT_TOKENS)


def _collect_desk_articles(
    tags: Optional[List[str]],
    sentiments: Optional[List[str]],
    keywords: Optional[List[str]],
    tag_mode: str,
    article_ids: Optional[List[int]],
    time_from: str,
    time_to: str,
):
    from app.services.market_desk import decorate_articles

    by_id = {}
    if article_ids:
        for art in db.get_articles_by_ids(article_ids):
            by_id[art.id] = art
    for art in db.get_articles(
        tags=tags,
        sentiments=sentiments,
        keywords=keywords,
        tag_mode=tag_mode or "union",
        time_from=time_from,
        time_to=time_to,
        limit=CHAT_ARTICLE_LIMIT,
    ):
        by_id[art.id] = art
    articles = list(by_id.values())
    articles.sort(key=lambda a: a.published_at or a.fetched_at or "", reverse=True)
    return decorate_articles(articles)


def answer_desk_question(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    tags: Optional[List[str]] = None,
    sentiments: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    tag_mode: str = "union",
    article_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    win_from, win_to = db.get_rolling_window()
    dashboard = db.get_dashboard_mode(
        tags=tags,
        time_from=win_from,
        time_to=win_to,
        tag_mode=tag_mode or "union",
        sentiments=sentiments,
        keywords=keywords,
    )
    dashboard = dashboard.model_copy(update={"window_from": win_from, "window_to": win_to})
    from app.services.market_desk import build_tape

    articles = _collect_desk_articles(
        tags=tags,
        sentiments=sentiments,
        keywords=keywords,
        tag_mode=tag_mode or "union",
        article_ids=article_ids,
        time_from=win_from,
        time_to=win_to,
    )
    tags_meta = db.get_all_tags_with_metadata(time_from=win_from, time_to=win_to)
    tape = build_tape(articles)
    corpus = _build_corpus(articles)
    snapshot = _desk_snapshot(dashboard, tags_meta, []) + "\n" + _tape_snapshot(tape)

    read_ids = _select_related(message, corpus, CHAT_READ_LIMIT)
    parsed = _answer_from_reads(message, history or [], snapshot, corpus, read_ids)
    if parsed:
        answer = str(parsed.get("answer") or "").strip()
        raw_ids = parsed.get("citation_ids") or read_ids
        try:
            citation_ids = [int(x) for x in raw_ids]
        except (TypeError, ValueError):
            citation_ids = list(read_ids)
    else:
        answer, citation_ids = _keyword_fallback(message, corpus)

    citation_ids = _extract_ids(answer, citation_ids, len(corpus))
    if corpus and not citation_ids:
        citation_ids = list(read_ids)

    if citation_ids and not re.search(r"\[\d+\]", answer):
        answer = answer.rstrip() + " " + "".join(f"[{i}]" for i in citation_ids)

    citations = []
    for i in citation_ids:
        item = corpus[i - 1]
        citations.append(
            {
                "id": i,
                "title": item["title"],
                "source_name": item["source_name"],
                "url": item["url"],
                "sentiment_label": item["sentiment_label"],
                "tags": item["tags"],
            }
        )
    logger.info(
        "chat agent read=%s citations=%s desk=%s chars=%s",
        read_ids,
        citation_ids,
        len(corpus),
        len(answer),
    )
    return {"answer": answer, "citations": citations, "desk_count": len(corpus)}
