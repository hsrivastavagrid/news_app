import json
import logging
import re
from typing import Optional
from app.config import DOMAIN_TAGS, GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL

logger = logging.getLogger("newspulse.agent")
from app.models import AgentFilterResponse, PreferenceSchema

VALID_SENTIMENTS = {"good", "bad", "ugly", "neutral"}

AGENT_SYSTEM = """You are a news-priority filter agent for NewsPulse.
Convert the user's request into JSON filters for their personalized hourly feed.

Valid tags (use only these): politics, finance, tech, health, sports, science, entertainment, world
Valid sentiments (use only these): good, bad, ugly, neutral

Rules:
- tags: domains the user wants. Empty means all domains.
- sentiments: modes to KEEP. If they say "no ugly" omit ugly. If they say "only good" return ["good"].
- keywords: extra phrases to match in title/description (tickers like NVDA, Fed, earnings). Empty means no keyword constraint.
- tag_mode: "union" (any selected tag — default for personalization) unless they explicitly want stories that match ALL tags ("intersection").
- explanation: one short sentence describing the filter.

Return ONLY JSON:
{"tags":[],"sentiments":[],"keywords":[],"tag_mode":"union","explanation":""}
"""


def _normalize(parsed: dict, explanation_fallback: str = "") -> AgentFilterResponse:
    tags = [t for t in parsed.get("tags") or [] if str(t).lower() in DOMAIN_TAGS]
    sentiments = [s for s in parsed.get("sentiments") or [] if str(s).lower() in VALID_SENTIMENTS]
    keywords = [str(k).strip() for k in parsed.get("keywords") or [] if str(k).strip()]
    tag_mode = str(parsed.get("tag_mode") or "union").lower()
    if tag_mode not in ("union", "intersection"):
        tag_mode = "union"
    if not sentiments:
        sentiments = ["good", "bad", "ugly", "neutral"]
    return AgentFilterResponse(
        tags=tags,
        sentiments=sentiments,
        keywords=keywords,
        tag_mode=tag_mode,
        explanation=str(parsed.get("explanation") or explanation_fallback),
        persisted=False,
    )


def heuristic_parse(message: str) -> AgentFilterResponse:
    """Offline fallback when GROQ_API_KEY is not set."""
    logger.info("agent heuristic parse")
    text = (message or "").lower()
    tags = [t for t in DOMAIN_TAGS if re.search(r"\b" + re.escape(t) + r"\b", text)]
    if "technology" in text and "tech" not in tags:
        tags.append("tech")
    if "business" in text or "market" in text or "stock" in text or "trader" in text or "earnings" in text:
        if "finance" not in tags:
            tags.append("finance")

    sentiments = set(VALID_SENTIMENTS)
    if re.search(r"\bno ugly\b|\bskip ugly\b|\bwithout ugly\b|\bnot ugly\b", text):
        sentiments.discard("ugly")
    if re.search(r"\bonly good\b|\bjust good\b|\bpositive only\b", text):
        sentiments = {"good"}
    if re.search(r"\bonly ugly\b|\bjust ugly\b", text):
        sentiments = {"ugly"}
    if re.search(r"\bno bad\b|\bskip bad\b", text):
        sentiments.discard("bad")
    if "good" in text and "only" not in text and "just" not in text:
        pass
    for s in VALID_SENTIMENTS:
        if re.search(rf"\bonly {s}\b", text):
            sentiments = {s}

    tag_mode = "intersection" if re.search(r"\bboth\b|\ball of\b|\bintersection\b", text) else "union"

    stop = {
        "show", "me", "news", "about", "the", "and", "or", "only", "just", "skip", "without",
        "not", "no", "please", "want", "priority", "priorities", "articles", "hourly",
        "good", "bad", "ugly", "neutral", "tag", "tags", "filter", "filters",
        *DOMAIN_TAGS, "technology", "business",
    }
    keywords = []
    for token in re.findall(r"[a-z0-9][a-z0-9\-]{1,}", text):
        if token not in stop and token not in tags:
            keywords.append(token)
    # keep unique, max 8
    seen = []
    for k in keywords:
        if k not in seen:
            seen.append(k)
    keywords = seen[:8]

    if GROQ_API_KEY:
        explanation = (
            f"Heuristic filter (Groq call failed for {GROQ_MODEL}; see logs)."
        )
    else:
        explanation = "Heuristic filter from your request (no LLM key configured)."
    return _normalize(
        {
            "tags": tags,
            "sentiments": sorted(sentiments),
            "keywords": keywords,
            "tag_mode": tag_mode,
            "explanation": explanation,
        },
        explanation,
    )


def llm_parse(message: str) -> Optional[AgentFilterResponse]:
    if not GROQ_API_KEY:
        logger.info("groq skipped: GROQ_API_KEY not set")
        return None
    try:
        logger.info("groq request model=%s", GROQ_MODEL)
        from openai import OpenAI

        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": message},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
        result = _normalize(parsed)
        if not result.explanation:
            result.explanation = "Filter updated from your request."
        logger.info("groq parse ok tags=%s sentiments=%s", result.tags, result.sentiments)
        return result
    except Exception:
        logger.exception("groq parse failed; falling back to heuristic")
        return None


def parse_priority_message(message: str) -> AgentFilterResponse:
    return llm_parse(message) or heuristic_parse(message)


def to_preferences(result: AgentFilterResponse) -> PreferenceSchema:
    return PreferenceSchema(
        tags=result.tags,
        sentiments=result.sentiments,
        keywords=result.keywords,
        tag_mode=result.tag_mode,
    )
