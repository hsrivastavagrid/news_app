# NewsPulse — Decision Log

> **Purpose:** Quick-reference for *why* each decision was made. Read this first after a context window reset.
> **Last updated:** Aug 26, 2026

---

## 1. Project Goal (The "What")

Build an hourly news sentiment dashboard that classifies headlines into **4 modes — Good / Bad / Ugly / Neutral**. The landing page shows the **overall mode** across all news. **Domain tags** (politics, finance, tech, health, sports, science, entertainment, world) each display their own per-tag mode. Users can **multi-select tags** — the dashboard recalculates mode, charts, and feed on the **intersection** (articles tagged with ALL selected tags). The USP is **cross-domain sentiment contagion detection**.

---

## 2. Why These APIs

| Decision | Rationale |
|---|---|
| **GNews.io (primary)** | Free tier: 100 req/day, 10 articles/req. Has built-in `category` param (general, world, business, tech, etc.) that maps to our domain tags with no scraping needed. Email-only signup, no credit card. |
| **Currents API (fallback)** | 250 req/day free. Different source pool — if GNews is rate-limited or down, we don't lose an hourly cycle. |
| **Why not NewsAPI.org?** | Free tier only works on `localhost` — breaks on deploy. GNews has no such restriction. |
| **Why not freenewsapi.ai?** | No API key = no rate-limit accountability. Unstable for production. |

---

## 3. Why VADER for Sentiment

| Decision | Rationale |
|---|---|
| **VADER over TextBlob** | VADER is tuned for news/social text — handles punctuation intensity ("AMAZING!!!"), caps, conjunctions ("good but not great"). TextBlob is more generic. |
| **VADER over Transformers** | 1.5-day deadline. VADER: zero training, ~1MB, microseconds/headline. DistilBERT: needs `torch` (~2GB), GPU, model download. Overkill for headline-level classification. |
| **Why not pre-built sentiment API?** | Tight free tier limits, vendor dependency for core logic, and we lose custom "ugly" classification control. |

---

## 4. Why the 4-Class System (Good/Bad/Ugly/Neutral)

| Decision | Rationale |
|---|---|
| **Ugly ≠ Bad** | "Bad" = negative sentiment (stock drop, policy failure). "Ugly" = *disturbing, scandalous, outrageous* (corruption, violence, fraud). Ugly news drives viral engagement and PR crises — it needs a different response playbook than merely "bad" news. |
| **Compound -0.05 for bad, -0.3 + keywords for ugly** | VADER compound ranges -1 to +1. Standard cutoff is ±0.05. We add a keyword layer: a headline needs both strong negativity AND disturbing keywords for "ugly". Prevents false positives (e.g., "stocks crash" = bad, not ugly). |
| **Ugly at -0.5 even without keywords** | Extremely negative compound scores indicate something deeply negative even if our keyword list doesn't catch the exact word. Safety net for rare phrasing. |

---

## 5. Why Multi-Tag Instead of Separate Sections

| Decision | Rationale |
|---|---|
| **User requirement (revised)** | User explicitly replaced the 3-section layout (Broad/Politics/Finance) with a unified view. Landing page = overall mode. Tags = multi-select drill-down. |
| **Multi-tag per article** | Real news crosses domains. "Lawmakers accused of insider trading" is BOTH politics AND finance. A single-sector column forces a false choice. Multi-tag captures reality. |
| **Junction table (article_tags)** | Many-to-many relationship requires a junction table. One article → many tags. One tag → many articles. This is the standard relational pattern. |
| **Why not a comma-separated tags column?** | Can't index it. Can't do efficient intersection queries. SQL JOINs on a junction table are fast and clean. |

---

## 6. Why Intersection (AND), Not Union (OR)

| Decision | Rationale |
|---|---|
| **Intersection = the unique feature** | Union (OR) is what every filter does — just "show me politics OR finance." Intersection (AND) answers a much more powerful question: "show me articles that are BOTH political AND financial." That's where cross-domain stories live — the exact stories that drive contagion. |
| **User explicitly requested this** | "If more than one tag is selected, then the news shown should only be the intersection subset of selected tags." |
| **Dynamic mode on intersection** | The mode (Good/Bad/Ugly/Neutral) recalculates on the intersection subset. So selecting Politics+Finance might show "Ugly" even when Politics alone is "Bad" and Finance alone is "Good" — because the cross-domain stories are disproportionately scandalous. This is a genuinely novel insight you can't get from separate section views. |
| **Implementation: N JOINs** | For each selected tag, add one JOIN to the query. Only articles surviving ALL joins appear. Simple, fast, correct. Built dynamically in Python from the `selectedTags` list. |

---

## 7. Why Per-Tag Mode Badges on the Tag Bar

| Decision | Rationale |
|---|---|
| **At-a-glance scanning** | A stakeholder sees 8 tag pills and instantly knows which domains are "Good" vs "Ugly" without clicking anything. 2-second scan replaces 8 separate dashboard views. |
| **Computed from tag_snapshots** | Each tag's mode is the dominant sentiment (highest count) among its articles. Pre-computed hourly via `tag_snapshots` table, not computed on every page load. |
| **Mode badge = emoji + label** | 😊 GOOD / 😞 BAD / 💀 UGLY / 😐 NEUTRAL — universally readable, no colour-blindness issues (emoji + text, not just colour). |

---

## 8. Why Cross-Domain Contagion (The USP)

| Decision | Rationale |
|---|---|
| **Why this USP?** | The 4-mode classification is a PRD requirement, not a differentiator. Multi-tag intersection is a unique UI feature but not a "stakeholder pitch." Contagion detection — "Politics went ugly, Finance will follow in 3 hours" — is the kind of predictive signal that makes executives sit up. |
| **Adapted for tag-based architecture** | Previously compared 3 fixed sectors. Now compares all tag-pairs dynamically (politics↔finance, finance↔tech, etc.). Same sliding-window delta logic, just more pairs to check. |
| **Why it's not complex** | Delta-comparison between tag compound scores over 2h windows. ~50 lines of Python. No ML, no training data. If Tag A drops >0.3 and Tag B hasn't moved yet → alert. |
| **Stakeholder value** | Investment analysts, PR teams, campaign managers get advance warning of sentiment ripple effects across domains. Transforms dashboard from "reporting tool" to "early warning system." |

---

## 9. Why SQLite

| Decision | Rationale |
|---|---|
| **Zero setup** | Ships with Python. No server process. Perfect for 1.5-day deadline. |
| **Junction table works fine** | Some worry about SQLite + JOINs, but our data volume is tiny (~700 articles/day). JOIN performance is instant. |
| **SQL for intersection queries** | The multi-tag intersection query (N JOINs) is clean SQL. Flat files would need custom Python set logic on every request. |
| **Future upgrade** | Swap `sqlite3` for `asyncpg` (Postgres) with minimal code changes if it scales. |

---

## 10. Why FastAPI

| Decision | Rationale |
|---|---|
| **FastAPI over Flask** | Async for `httpx` API calls, auto Swagger docs at `/docs`, Pydantic validation out of the box. |
| **FastAPI over Django** | Too heavy. No need for ORM, admin, templates, or auth. |
| **`tags` as comma-separated query param** | `?tags=politics,finance` is simple, URL-shareable, and maps directly to frontend state. No complex request body needed for reads. |

---

## 11. Why APScheduler

| Decision | Rationale |
|---|---|
| **APScheduler over cron** | In-process Python scheduler. Portable. Triggerable via `/api/fetch-now`. No OS config needed. |
| **APScheduler over Celery** | Celery needs Redis/RabbitMQ. Overkill for one hourly job. |
| **Pipeline: fetch → tag → analyze → snapshot → contagion** | Each step feeds the next. All run synchronously inside one scheduled job. Tag snapshots are written per-tag so the tag bar can show fresh modes. |

---

## 12. Why This Frontend Architecture

| Decision | Rationale |
|---|---|
| **Vanilla HTML/CSS/JS** | 1.5-day deadline. No build step, no npm. The dashboard is one page with dynamic re-rendering — doesn't need React/Vue component trees. |
| **`selectedTags = []` state array** | The entire UI is driven by this one piece of state. Empty = overall view. Non-empty = intersection view. Every fetch includes `?tags=${selectedTags.join(',')}`. |
| **Chart.js destroy + re-create** | When tags change, we destroy the old Chart.js instances and create new ones with the new data. Simpler and more reliable than trying to update data in-place (Chart.js has known quirks with dynamic updates). |
| **Single dashboard, not separate sections** | User's explicit requirement. One unified view that reacts to tag selection is more powerful and less visually cluttered than 3+ fixed sections. |

---

## 13. Why This Visual Design

| Decision | Rationale |
|---|---|
| **Glassmorphism** | Frosted-glass on dark gradient = premium feel with minimal CSS. `backdrop-filter: blur()` is widely supported. |
| **Ugly = purple (#7C3AED)** | If ugly were another shade of red, it would blend with "bad." Purple stands out immediately. |
| **Tag pill accents** | 8 unique subtle accent colours per tag pill so users visually distinguish domains at a glance. Colours don't carry semantic weight — the mode badge does. |
| **Overall mood hero section** | Large, prominent mode display at the top. When no tags are selected, this IS the dashboard. Establishes the "broader view first" hierarchy the user requested. |
| **Selected tags bar** | Shows active tags with ✕ dismiss buttons + intersection article count. Provides clear state indication and easy deselection. |

---

## 14. Why This Fetch Strategy

| Decision | Rationale |
|---|---|
| **4 categories/hour, rotating** | Cycle through 8 GNews categories in 2 batches. 4 req/hr × 24h = 96/day (under 100 limit). More categories than before (8 vs 3) because multi-tag needs broader coverage. |
| **Dedup by URL hash (SHA256)** | Same article can appear across hourly windows. Hash the URL, `UNIQUE` constraint handles the rest. |
| **Multi-tag assignment happens after fetch** | Fetch is category-specific (GNews constraint), but an article from `category=general` could get tagged `politics` + `finance` via keyword matching. Tag assignment is a second pass on every fetched article. |
| **Keyword threshold ≥ 2** | Prevents single-word false positives. "policy" alone doesn't tag as "politics" — you need 2+ keyword hits. |

---

## 15. Key Thresholds Reference

| Threshold | Value | Why |
|---|---|---|
| VADER "good" | compound ≥ 0.05 | Standard VADER positive cutoff |
| VADER "bad" | compound ≤ -0.05 | Standard VADER negative cutoff |
| VADER "ugly" (with keywords) | compound ≤ -0.3 + ≥1 ugly keyword | Must be notably negative AND contain disturbing language |
| VADER "ugly" (no keywords) | compound ≤ -0.5 | Safety net for extremely negative text |
| Tag assignment threshold | ≥ 2 keyword hits per tag | Prevents false positives from single ambiguous words |
| Contagion trigger | Δ compound > 0.3 in 2h | 0.3 on a -1 to +1 scale is significant. 2h window balances speed vs noise |

---

## 16. DB Schema Quick Reference

| Table | Purpose | Key Design Choice |
|---|---|---|
| `articles` | All fetched articles + sentiment scores | No `sector`/`tag` column — tags live in junction table |
| `article_tags` | Junction: article ↔ tags (many-to-many) | `PRIMARY KEY (article_id, tag)` prevents duplicates |
| `tag_snapshots` | Per-tag hourly aggregates | Used for trend charts and contagion detection. `UNIQUE(snapshot_time, tag)` |
| `contagion_events` | Cross-domain alerts | `source_tag` → `target_tag`. `resolved` tracks if prediction came true |

---

## 17. API Quick Reference

| Endpoint | `tags` param | Behaviour |
|---|---|---|
| `GET /api/dashboard` | omitted | Overall mode (all articles) |
| `GET /api/dashboard?tags=finance` | single | Mode for finance-tagged articles only |
| `GET /api/dashboard?tags=politics,finance` | multi | Mode for INTERSECTION (articles with BOTH tags) |
| `GET /api/tags` | N/A | Returns all 8 tags with per-tag mode badge + article count |
| `GET /api/articles?tags=X,Y&sentiment=ugly` | multi | Intersection articles, filtered by sentiment |
| `GET /api/contagion` | N/A | Active cross-domain alerts |

---

## 18. File-to-Responsibility Map

| File | What It Does | Key Decision |
|---|---|---|
| `app/main.py` | FastAPI routes + startup + static serving | `tags` is a comma-separated query param, not separate endpoints |
| `app/config.py` | Env vars, TAG_KEYWORDS dict, UGLY_KEYWORDS, thresholds | All magic numbers and keyword sets live here — single source of truth |
| `app/models.py` | Pydantic models / dataclasses | `TaggedArticle` has a `tags: list[str]` field |
| `app/database/db.py` | SQLite CRUD + intersection query builder | Dynamically builds N-JOIN queries from tag list. Raw SQL, no ORM |
| `app/database/schema.sql` | Table definitions | 4 tables: articles, article_tags, tag_snapshots, contagion_events |
| `app/services/news_fetcher.py` | API calls + multi-tag assignment | Assigns ≥1 tag per article. GNews category = base tag, keywords = additional tags |
| `app/services/sentiment_analyzer.py` | VADER + ugly + contagion + intersection mode | `compute_intersection_mode()` recalculates mode on any filtered article subset |
| `app/services/scheduler.py` | APScheduler config | Triggers: fetch → tag → analyze → snapshot → contagion pipeline |
| `app/static/index.html` | Unified dashboard HTML | One page: hero mode + tag bar + filtered view panel |
| `app/static/style.css` | All styling | Tag pill components, glassmorphism, 8 tag accent colours |
| `app/static/app.js` | Tag state + dynamic re-rendering | `selectedTags[]` drives all fetches. Charts rebuilt on tag change |
