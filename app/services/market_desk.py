"""Headline → issuer / event / desk-signal for a trader tape.

This is not a price feed and not investment advice. It maps the stories already
on the desk to named companies, market-event types, and a conservative
risk-on / risk-off / watch flag a trader can use to decide what to inspect.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.models import ArticleSchema, CompanyMention, TapeNameSchema, TapeSchema

MARKET_CONTEXT = re.compile(
    r"\b(stock|stocks|shares?|equity|equities|investor|investors|nasdaq|nyse|"
    r"dow|s&p|earnings|eps|guidance|ipo|dividend|buyback|upgrade|downgrade|"
    r"price target|market|markets|wall street|sec |fed |fomc|yield|"
    r"inflation|recession|merger|acquisition|bankruptcy)\b",
    re.I,
)

# ticker, name, sector, aliases, ambiguous (needs market context or $TICKER)
COMPANIES: List[Tuple[str, str, str, Tuple[str, ...], bool]] = [
    ("AAPL", "Apple", "tech", ("Apple Inc", "Apple's", "Apple", "iPhone", "AAPL"), True),
    ("MSFT", "Microsoft", "tech", ("Microsoft", "MSFT", "Azure", "OpenAI"), False),
    ("GOOGL", "Alphabet", "tech", ("Alphabet", "Google", "GOOGL", "GOOG", "YouTube"), False),
    ("AMZN", "Amazon", "consumer", ("Amazon", "AMZN", "AWS", "Amazon.com"), False),
    ("META", "Meta", "tech", ("Meta Platforms", "Facebook", "Instagram", "WhatsApp", "Meta", "META"), True),
    ("NVDA", "NVIDIA", "semis", ("NVIDIA", "Nvidia", "NVDA"), False),
    ("AVGO", "Broadcom", "semis", ("Broadcom", "AVGO"), False),
    ("TSM", "TSMC", "semis", ("TSMC", "Taiwan Semiconductor"), False),
    ("AMD", "AMD", "semis", ("Advanced Micro Devices", "AMD"), True),
    ("INTC", "Intel", "semis", ("Intel", "INTC"), False),
    ("QCOM", "Qualcomm", "semis", ("Qualcomm", "QCOM"), False),
    ("ASML", "ASML", "semis", ("ASML",), False),
    ("MU", "Micron", "semis", ("Micron", "MU"), True),
    ("SMCI", "Super Micro", "semis", ("Super Micro", "Supermicro", "SMCI"), False),
    ("ARM", "Arm", "semis", ("Arm Holdings", "ARM Holdings"), False),
    ("TSLA", "Tesla", "auto", ("Tesla", "TSLA", "Elon Musk"), False),
    ("F", "Ford", "auto", ("Ford Motor", "Ford's"), False),
    ("GM", "General Motors", "auto", ("General Motors", "GM"), True),
    ("RIVN", "Rivian", "auto", ("Rivian", "RIVN"), False),
    ("TM", "Toyota", "auto", ("Toyota",), False),
    ("CRM", "Salesforce", "tech", ("Salesforce", "CRM"), True),
    ("ORCL", "Oracle", "tech", ("Oracle", "ORCL"), False),
    ("ADBE", "Adobe", "tech", ("Adobe", "ADBE"), False),
    ("NFLX", "Netflix", "media", ("Netflix", "NFLX"), False),
    ("DIS", "Disney", "media", ("Disney", "Walt Disney", "DIS"), True),
    ("SPOT", "Spotify", "media", ("Spotify",), False),
    ("BABA", "Alibaba", "consumer", ("Alibaba", "BABA"), False),
    ("SHOP", "Shopify", "consumer", ("Shopify", "SHOP"), True),
    ("JPM", "JPMorgan", "finance", ("JPMorgan", "JP Morgan", "JPM", "Jamie Dimon"), False),
    ("BAC", "Bank of America", "finance", ("Bank of America", "BofA", "BAC"), True),
    ("WFC", "Wells Fargo", "finance", ("Wells Fargo", "WFC"), False),
    ("GS", "Goldman Sachs", "finance", ("Goldman Sachs", "Goldman"), False),
    ("MS", "Morgan Stanley", "finance", ("Morgan Stanley",), False),
    ("C", "Citigroup", "finance", ("Citigroup", "Citibank", "Citi"), False),
    ("V", "Visa", "finance", ("Visa Inc", "Visa's"), False),
    ("MA", "Mastercard", "finance", ("Mastercard", "MasterCard"), False),
    ("BRK.B", "Berkshire Hathaway", "finance", ("Berkshire Hathaway", "Berkshire", "Warren Buffett"), False),
    ("BLK", "BlackRock", "finance", ("BlackRock", "Blackrock"), False),
    ("SCHW", "Charles Schwab", "finance", ("Charles Schwab", "Schwab"), True),
    ("PYPL", "PayPal", "finance", ("PayPal", "PYPL"), False),
    ("COIN", "Coinbase", "crypto", ("Coinbase", "COIN"), False),
    ("HOOD", "Robinhood", "finance", ("Robinhood", "HOOD"), False),
    ("XOM", "Exxon Mobil", "energy", ("Exxon Mobil", "Exxon", "XOM"), False),
    ("CVX", "Chevron", "energy", ("Chevron", "CVX"), False),
    ("COP", "ConocoPhillips", "energy", ("ConocoPhillips", "COP"), True),
    ("BP", "BP", "energy", ("BP plc", "British Petroleum"), False),
    ("SHEL", "Shell", "energy", ("Shell plc", "Royal Dutch Shell"), False),
    ("SLB", "Schlumberger", "energy", ("Schlumberger", "SLB"), False),
    ("JNJ", "Johnson & Johnson", "health", ("Johnson & Johnson", "J&J", "JNJ"), False),
    ("PFE", "Pfizer", "health", ("Pfizer", "PFE"), False),
    ("UNH", "UnitedHealth", "health", ("UnitedHealth", "United Health", "UNH"), False),
    ("LLY", "Eli Lilly", "health", ("Eli Lilly", "Lilly", "LLY"), True),
    ("MRK", "Merck", "health", ("Merck", "MRK"), True),
    ("ABBV", "AbbVie", "health", ("AbbVie", "ABBV"), False),
    ("AMGN", "Amgen", "health", ("Amgen", "AMGN"), False),
    ("GILD", "Gilead", "health", ("Gilead", "GILD"), False),
    ("MRNA", "Moderna", "health", ("Moderna", "MRNA"), False),
    ("WMT", "Walmart", "consumer", ("Walmart", "Wal-Mart", "WMT"), False),
    ("COST", "Costco", "consumer", ("Costco", "COST"), False),
    ("HD", "Home Depot", "consumer", ("Home Depot",), False),
    ("TGT", "Target", "consumer", ("Target Corp", "Target's"), False),
    ("NKE", "Nike", "consumer", ("Nike", "NKE"), True),
    ("SBUX", "Starbucks", "consumer", ("Starbucks", "SBUX"), False),
    ("MCD", "McDonald's", "consumer", ("McDonald's", "McDonalds", "MCD"), False),
    ("KO", "Coca-Cola", "consumer", ("Coca-Cola", "Coca Cola"), False),
    ("PEP", "PepsiCo", "consumer", ("PepsiCo", "Pepsi"), False),
    ("PG", "Procter & Gamble", "consumer", ("Procter & Gamble", "P&G"), False),
    ("BA", "Boeing", "industrial", ("Boeing",), False),
    ("CAT", "Caterpillar", "industrial", ("Caterpillar", "CAT"), True),
    ("GE", "GE", "industrial", ("General Electric", "GE Aerospace"), False),
    ("HON", "Honeywell", "industrial", ("Honeywell",), False),
    ("DE", "Deere", "industrial", ("Deere", "John Deere"), False),
    ("UPS", "UPS", "industrial", ("United Parcel Service", "UPS"), True),
    ("FDX", "FedEx", "industrial", ("FedEx", "Fedex"), False),
    ("DAL", "Delta", "airlines", ("Delta Air", "Delta Airlines"), False),
    ("UAL", "United Airlines", "airlines", ("United Airlines",), False),
    ("AAL", "American Airlines", "airlines", ("American Airlines",), False),
    ("T", "AT&T", "telecom", ("AT&T", "AT&T Inc"), False),
    ("VZ", "Verizon", "telecom", ("Verizon",), False),
    ("TMUS", "T-Mobile", "telecom", ("T-Mobile", "T Mobile"), False),
    ("CMCSA", "Comcast", "media", ("Comcast", "CMCSA"), False),
    ("IBM", "IBM", "tech", ("IBM", "International Business Machines"), False),
    ("CSCO", "Cisco", "tech", ("Cisco", "CSCO"), False),
    ("NOW", "ServiceNow", "tech", ("ServiceNow", "NOW"), True),
    ("UBER", "Uber", "tech", ("Uber",), False),
    ("ABNB", "Airbnb", "consumer", ("Airbnb", "ABNB"), False),
    ("PLTR", "Palantir", "tech", ("Palantir", "PLTR"), False),
    ("SNOW", "Snowflake", "tech", ("Snowflake", "SNOW"), True),
    ("PANW", "Palo Alto Networks", "tech", ("Palo Alto Networks", "PANW"), False),
    ("CRWD", "CrowdStrike", "tech", ("CrowdStrike", "CRWD"), False),
]

MACRO: List[Tuple[str, str, str, Tuple[str, ...]]] = [
    ("SPX", "S&P 500", "index", ("s&p 500", "s&p500", "the s&p", "spx")),
    ("NDX", "Nasdaq", "index", ("nasdaq-100", "nasdaq composite", "the nasdaq")),
    ("DJI", "Dow Jones", "index", ("dow jones", "the dow", "djia", "dow industrials")),
    ("VIX", "VIX", "index", ("vix", "fear index", "volatility index")),
    ("US10Y", "US 10Y", "rates", ("10-year yield", "treasury yield", "bond yields", "ust 10y")),
    ("FOMC", "Federal Reserve", "rates", ("federal reserve", "the fed", "fomc", "jerome powell", "powell")),
    ("BTC", "Bitcoin", "crypto", ("bitcoin", "btc")),
    ("ETH", "Ethereum", "crypto", ("ethereum", "ether")),
    ("OIL", "Crude oil", "energy", ("crude oil", "wti", "brent crude", "oil prices")),
    ("GOLD", "Gold", "commodity", ("gold prices", "bullion", "spot gold")),
]

EVENT_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    ("bankruptcy", "Insolvency", re.compile(r"\b(bankrupt(?:cy)?|chapter\s*11|insolvent|default on|goes bust)\b", re.I)),
    ("lawsuit", "Legal", re.compile(r"\b(lawsuit|sued|class action|litigation|settlement|indicted)\b", re.I)),
    ("cyber", "Cyber", re.compile(r"\b(data breach|hack(?:ed|ing)?|ransomware|cyberattack|zero-?day)\b", re.I)),
    ("layoff", "Headcount", re.compile(r"\b(layoff|layoffs|job cuts?|workforce reduction|restructuring jobs|furlough)\b", re.I)),
    ("mna", "M&A", re.compile(r"\b(merger|acquisition|acquire[ds]?|takeover|buyout|deal to buy)\b", re.I)),
    ("ipo", "IPO", re.compile(r"\b(ipo|goes public|initial public offering|direct listing)\b", re.I)),
    ("earnings", "Earnings", re.compile(r"\b(earnings|eps|quarterly results|profit warning|beats? estimates|miss(?:ed|es)? estimates|revenue miss|revenue beat)\b", re.I)),
    ("guidance", "Guidance", re.compile(r"\b(guidance|outlook cut|outlook raise|cuts? forecast|raises? forecast)\b", re.I)),
    ("analyst", "Street view", re.compile(r"\b(upgrade[ds]?|downgrade[ds]?|price target|overweight|underweight|initiates coverage)\b", re.I)),
    ("dividend", "Capital return", re.compile(r"\b(dividend|buyback|share repurchase|special dividend)\b", re.I)),
    ("regulation", "Policy", re.compile(r"\b(antitrust|doj|ftc|sec charges|sanction[s]?|tariff[s]?|probe|investigation|fine[ds]?)\b", re.I)),
    ("rates", "Rates", re.compile(r"\b(interest rate|rate hike|rate cut|fomc|fed funds|quantitative tightening|qe\b)\b", re.I)),
    ("macro", "Macro", re.compile(r"\b(inflation|cpi|ppi|gdp|recession|unemployment|jobs report|nonfarm|pce)\b", re.I)),
    ("supply", "Supply", re.compile(r"\b(shortage|supply chain|chip shortage|disruption|recall)\b", re.I)),
    ("product", "Product", re.compile(r"\b(launch(?:es|ed)?|unveils|iphone|product delay|recall)\b", re.I)),
]

RISK_OFF_EVENTS = {"bankruptcy", "lawsuit", "cyber", "layoff", "regulation"}
RISK_ON_EVENTS = {"dividend", "ipo"}
MISS = re.compile(r"\b(miss(?:ed|es)?|slump|plunge|tumble|crash|collapse|warning|cuts? guidance|downgrade)\b", re.I)
BEAT = re.compile(r"\b(beat[s]?|surge|soar|rally|record high|raises? guidance|upgrade|buyback)\b", re.I)

DISCLAIMER = (
    "Headline risk only — named issuers and risk-on/off flags are inferred from "
    "this hour's stories, not live quotes or a buy/sell recommendation."
)


@dataclass
class MarketBrief:
    companies: List[CompanyMention] = field(default_factory=list)
    event_type: str = "general"
    event_label: str = "General"
    signal: str = "watch"
    thesis: str = ""


WEAK_NAMES = {
    "apple", "meta", "target", "ford", "visa", "cat", "now", "snow", "shop",
    "lilly", "merck", "nike", "amd", "schwab", "gm", "bac", "dis", "cost",
    "cop", "mu", "crm", "ups",
}


def _word_hit(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return re.search(r"(?<![A-Za-z0-9.&])" + re.escape(needle) + r"(?![A-Za-z0-9.&-])", haystack, re.I) is not None


def _ticker_hit(text: str, ticker: str) -> bool:
    escaped = re.escape(ticker)
    if re.search(rf"\${escaped}\b", text, re.I):
        return True
    if re.search(rf"\b(?:NASDAQ|NYSE|AMEX|TICKER)\s*:\s*{escaped}\b", text, re.I):
        return True
    if re.search(rf"\({escaped}\)", text, re.I):
        return True
    if len(ticker) >= 3 and re.search(rf"\b{escaped}\b", text):
        # Prefer uppercase ticker tokens in the original string.
        if re.search(rf"\b{escaped}\b", text):
            return True
    return False


def extract_companies(title: str, description: Optional[str] = None) -> List[CompanyMention]:
    blob = f"{title or ''} {description or ''}"
    ctx = bool(MARKET_CONTEXT.search(blob))
    found: Dict[str, CompanyMention] = {}

    for ticker, name, sector, aliases, ambiguous in COMPANIES:
        ticker_token = ticker.split(".")[0]
        strong = _ticker_hit(blob, ticker_token)
        weak = False
        for alias in aliases:
            if not _word_hit(blob, alias):
                continue
            if alias.lower() in WEAK_NAMES:
                weak = True
            else:
                strong = True
        if not strong and not weak:
            continue
        if ambiguous and not strong and not ctx:
            continue
        found[ticker] = CompanyMention(ticker=ticker, name=name, sector=sector)

    if ctx or found:
        lower = blob.lower()
        for ticker, name, sector, aliases in MACRO:
            if ticker in found:
                continue
            if any(alias in lower for alias in aliases):
                found[ticker] = CompanyMention(ticker=ticker, name=name, sector=sector)

    # Stable order: companies first (alpha ticker), then macro.
    names = list(found.values())
    names.sort(key=lambda c: (0 if c.sector not in {"index", "rates", "crypto", "commodity"} else 1, c.ticker))
    return names[:8]


def classify_event(title: str, description: Optional[str] = None) -> Tuple[str, str]:
    blob = f"{title or ''} {description or ''}"
    for key, label, pattern in EVENT_PATTERNS:
        if pattern.search(blob):
            return key, label
    if MARKET_CONTEXT.search(blob):
        return "macro", "Macro"
    return "general", "General"


def classify_signal(sentiment: str, event_type: str, title: str, description: Optional[str] = None) -> str:
    blob = f"{title or ''} {description or ''}"
    sent = (sentiment or "neutral").lower()
    if event_type in RISK_OFF_EVENTS or sent == "ugly" or MISS.search(blob):
        if sent in {"bad", "ugly"} or event_type in {"bankruptcy", "cyber", "layoff"}:
            return "risk_off"
    if event_type in RISK_ON_EVENTS or (sent == "good" and BEAT.search(blob)):
        return "risk_on"
    if sent == "good" and event_type in {"earnings", "product", "mna", "guidance"}:
        return "risk_on"
    if sent in {"bad", "ugly"}:
        return "risk_off"
    return "watch"


def _thesis(companies: Sequence[CompanyMention], event_label: str, signal: str, sentiment: str) -> str:
    names = ", ".join(c.ticker for c in companies[:3]) or "the tape"
    action = {
        "risk_off": "risk-off — inspect size, hedges, and whether the print can gap the name",
        "risk_on": "risk-on — watch for follow-through vs the headline, not a chase signal",
        "watch": "watch — relevant to the book, not a directional call yet",
    }[signal]
    return f"{names} · {event_label} · {action} (desk mood {sentiment})."


def analyze_story(title: str, description: Optional[str], sentiment: str = "neutral") -> MarketBrief:
    companies = extract_companies(title, description)
    event_type, event_label = classify_event(title, description)
    signal = classify_signal(sentiment, event_type, title, description)
    if not companies and event_type == "general":
        thesis = ""
    else:
        thesis = _thesis(companies, event_label, signal, sentiment)
    return MarketBrief(
        companies=companies,
        event_type=event_type,
        event_label=event_label,
        signal=signal,
        thesis=thesis,
    )


def decorate_article(article: ArticleSchema) -> ArticleSchema:
    brief = analyze_story(article.title, article.description, article.sentiment_label)
    return article.model_copy(
        update={
            "companies": brief.companies,
            "event_type": brief.event_type,
            "event_label": brief.event_label,
            "signal": brief.signal,
            "thesis": brief.thesis,
        }
    )


def decorate_articles(articles: Iterable[ArticleSchema]) -> List[ArticleSchema]:
    return [decorate_article(a) for a in articles]


def finance_tags_for(title: str, description: Optional[str], tags: List[str]) -> List[str]:
    """If a named issuer or market event is present, also file under finance."""
    brief = analyze_story(title, description)
    extra = set(tags)
    if brief.companies or brief.event_type not in {"general", "product"}:
        extra.add("finance")
    return sorted(extra)


SIGNAL_RANK = {"risk_off": 0, "watch": 1, "risk_on": 2}


def build_tape(articles: Sequence[ArticleSchema]) -> TapeSchema:
    decorated = [decorate_article(a) for a in articles]
    buckets: Dict[str, Dict[str, Any]] = {}
    for art in decorated:
        brief_cos = art.companies or []
        if not brief_cos:
            continue
        for co in brief_cos:
            row = buckets.setdefault(
                co.ticker,
                {
                    "ticker": co.ticker,
                    "name": co.name,
                    "sector": co.sector,
                    "signals": [],
                    "events": [],
                    "count": 0,
                    "compounds": [],
                    "headlines": [],
                    "sentiment": art.sentiment_label,
                },
            )
            row["count"] += 1
            row["signals"].append(art.signal or "watch")
            if art.event_label and art.event_label not in row["events"]:
                row["events"].append(art.event_label)
            row["compounds"].append(art.compound_score)
            if art.title not in row["headlines"]:
                row["headlines"].append(art.title)

    names: List[TapeNameSchema] = []
    for row in buckets.values():
        signal = "watch"
        if "risk_off" in row["signals"]:
            signal = "risk_off"
        elif row["signals"] and all(s == "risk_on" for s in row["signals"]):
            signal = "risk_on"
        avg = sum(row["compounds"]) / len(row["compounds"]) if row["compounds"] else 0.0
        events = row["events"][:3] or ["General"]
        thesis = _thesis(
            [CompanyMention(ticker=row["ticker"], name=row["name"], sector=row["sector"])],
            events[0],
            signal,
            "mixed" if len(set(row["signals"])) > 1 else signal,
        )
        names.append(
            TapeNameSchema(
                ticker=row["ticker"],
                name=row["name"],
                sector=row["sector"],
                signal=signal,
                event_types=events,
                article_count=row["count"],
                avg_compound=round(avg, 4),
                headlines=row["headlines"][:3],
                thesis=thesis,
            )
        )

    names.sort(key=lambda n: (SIGNAL_RANK.get(n.signal, 9), -n.article_count, n.ticker))
    names = names[:16]
    return TapeSchema(
        names=names,
        risk_off_count=sum(1 for n in names if n.signal == "risk_off"),
        risk_on_count=sum(1 for n in names if n.signal == "risk_on"),
        watch_count=sum(1 for n in names if n.signal == "watch"),
        name_count=len(names),
        disclaimer=DISCLAIMER,
    )
