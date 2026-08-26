import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL
from app.database import db
from app.urls import source_article_url

logger = logging.getLogger("newspulse.chat")

CHAT_SYSTEM = """You are the NewsPulse markets-desk correspondent. You sit on the same tape as the dashboard.

RULES:
1. Answer ONLY using the DESK SNAPSHOT, TRADER TAPE, and numbered ARTICLES below.
2. Every factual sentence MUST include at least one citation like [1] or [3] matching those article numbers.
3. Never invent headlines, tickers, prices, numbers, or URLs. If the desk does not contain the answer, say so and cite the closest articles.
4. You MAY use dashboard stats and the tape (issuers, event types, risk-on/off). Still cite supporting articles when you mention a name.
5. Frame signals as headline risk a trader would watch (size, hedge, gap risk) — NEVER as personalized buy/sell advice or a price target.
6. Do not truncate: write complete sentences. Prefer 2–6 short paragraphs.
7. Return JSON only:
{"answer":"markdown text with [n] citations","citation_ids":[1,3]}
citation_ids must be integers that appear in the answer.
"""


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
                "description": (art.description or "")[:500],
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
            "neutral={n} avg_compound={c} window={wf}..{wt} tags={tags}".format(
                mode=dashboard.dominant_mode,
                total=dashboard.total_articles,
                g=dashboard.good_count,
                b=dashboard.bad_count,
                u=dashboard.ugly_count,
                n=dashboard.neutral_count,
                c=dashboard.avg_compound,
                wf=dashboard.window_from,
                wt=dashboard.window_to,
                tags=dashboard.selected_tags,
            )
        )
    if tags_meta:
        bits = [f"{t.tag}:{t.dominant_mode}({t.article_count})" for t in tags_meta]
        lines.append("TAG MODES: " + "; ".join(bits))
    if alerts:
        lines.append("CONTAGION: " + " | ".join(a.message for a in alerts[:4]))
    return "\n".join(lines) or "DASHBOARD: empty"


def _tape_snapshot(tape) -> str:
    if not tape or not getattr(tape, "names", None):
        return "TAPE: no named issuers this hour."
    bits = [
        f"{n.ticker}:{n.signal}:{n.article_count}x:{','.join(n.event_types)}"
        for n in tape.names[:12]
    ]
    return (
        f"TAPE: names={tape.name_count} risk_off={tape.risk_off_count} "
        f"risk_on={tape.risk_on_count} watch={tape.watch_count} | "
        + "; ".join(bits)
    )


def _articles_block(corpus: List[Dict[str, Any]]) -> str:
    rows = []
    for item in corpus:
        rows.append(
            "[{id}] {title} | source={source} | sentiment={sent} | tags={tags} "
            "| tickers={tickers} | event={event} | signal={signal} | url={url}\n"
            "    {desc}\n    {thesis}".format(
                id=item["id"],
                title=item["title"],
                source=item["source_name"],
                sent=item["sentiment_label"],
                tags=",".join(item["tags"]),
                tickers=",".join(item.get("tickers") or []) or "-",
                event=item.get("event_type") or "general",
                signal=item.get("signal") or "watch",
                url=item["url"] or "(no publisher url)",
                desc=item["description"] or "",
                thesis=item.get("thesis") or "",
            )
        )
    return "\n".join(rows) if rows else "No articles on the desk this hour."


def _extract_ids(text: str, citation_ids: List[int], n: int) -> List[int]:
    found = [int(x) for x in re.findall(r"\[(\d+)\]", text or "")]
    merged = []
    for i in found + list(citation_ids or []):
        if 1 <= i <= n and i not in merged:
            merged.append(i)
    return merged


def _keyword_fallback(question: str, corpus: List[Dict[str, Any]]) -> Tuple[str, List[int]]:
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", (question or "").lower()) if t not in {
        "the", "and", "what", "who", "how", "why", "this", "hour", "news", "about", "tell", "from",
    }]
    scored = []
    for item in corpus:
        blob = (
            f"{item['title']} {item['description']} {' '.join(item['tags'])} "
            f"{' '.join(item.get('tickers') or [])} {' '.join(item.get('companies') or [])} "
            f"{item.get('event_type') or ''} {item.get('signal') or ''}"
        ).lower()
        hits = sum(1 for t in tokens if t in blob)
        scored.append((hits, item))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    picked = [item for hits, item in scored if hits > 0][:5] or [c for _, c in scored[:3]]
    if not picked:
        return (
            "This hour's desk has no matching stories I can cite. Fetch news or widen filters.",
            [],
        )
    lines = []
    ids = []
    for item in picked:
        ids.append(item["id"])
        lines.append(f"- {item['title']} ({item['source_name']}, {item['sentiment_label']}) [{item['id']}]")
    answer = (
        "I could not reach the language model, so here are cited stories from this hour's desk:\n"
        + "\n".join(lines)
    )
    return answer, ids


def _groq_answer(question: str, history: List[Dict[str, str]], snapshot: str, corpus: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not GROQ_API_KEY:
        logger.info("chat groq skipped: no key")
        return None
    messages = [
        {"role": "system", "content": CHAT_SYSTEM},
        {
            "role": "user",
            "content": f"{snapshot}\n\nARTICLES:\n{_articles_block(corpus)}\n",
        },
    ]
    for turn in history[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": question})
    try:
        from openai import OpenAI

        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        logger.info("chat groq request model=%s articles=%s", GROQ_MODEL, len(corpus))
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            max_tokens=2048,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        logger.exception("chat groq failed")
    return None


def answer_desk_question(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    tags: Optional[List[str]] = None,
    sentiments: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    tag_mode: str = "union",
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
    from app.services.market_desk import build_tape, decorate_articles

    articles = decorate_articles(
        db.get_articles(
            tags=tags,
            sentiments=sentiments,
            keywords=keywords,
            tag_mode=tag_mode or "union",
            time_from=win_from,
            time_to=win_to,
            limit=40,
        )
    )
    tags_meta = db.get_all_tags_with_metadata(time_from=win_from, time_to=win_to)
    tape = build_tape(articles)
    corpus = _build_corpus(articles)
    snapshot = _desk_snapshot(dashboard, tags_meta, []) + "\n" + _tape_snapshot(tape)

    parsed = _groq_answer(message, history or [], snapshot, corpus)
    if parsed:
        answer = str(parsed.get("answer") or "").strip()
        raw_ids = parsed.get("citation_ids") or []
        try:
            citation_ids = [int(x) for x in raw_ids]
        except (TypeError, ValueError):
            citation_ids = []
    else:
        answer, citation_ids = _keyword_fallback(message, corpus)

    citation_ids = _extract_ids(answer, citation_ids, len(corpus))
    if corpus and not citation_ids:
        answer, citation_ids = _keyword_fallback(message, corpus)
        citation_ids = _extract_ids(answer, citation_ids, len(corpus))

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
    logger.info("chat answer citations=%s chars=%s", citation_ids, len(answer))
    return {"answer": answer, "citations": citations}
