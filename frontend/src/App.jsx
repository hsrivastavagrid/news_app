import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { log } from "./logger.js";
import Sidebar from "./components/Sidebar.jsx";
import ArticleCard from "./components/ArticleCard.jsx";
import StatsBar from "./components/StatsBar.jsx";
import ChatBubble from "./components/ChatBubble.jsx";

const ALL_SENTIMENTS = ["good", "bad", "ugly", "neutral"];

function keywordsFromText(text) {
  return text
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

function formatWindow(fromIso, toIso) {
  if (!fromIso || !toIso) return "last hour";
  const parse = (v) => new Date(String(v).replace(" ", "T") + "Z");
  const a = parse(fromIso);
  const b = parse(toIso);
  if (Number.isNaN(a.getTime())) return "last hour";
  const opts = { hour: "2-digit", minute: "2-digit" };
  return `${a.toLocaleTimeString([], opts)} – ${b.toLocaleTimeString([], opts)}`;
}

export default function App() {
  const [tagsMeta, setTagsMeta] = useState([]);
  const [filters, setFilters] = useState({
    tags: [],
    sentiments: ALL_SENTIMENTS,
    keywordsText: "",
    tagMode: "union",
  });
  const [dashboard, setDashboard] = useState(null);
  const [articles, setArticles] = useState([]);
  const [agentNote, setAgentNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  const queryFilters = useMemo(
    () => ({
      tags: filters.tags,
      sentiments: filters.sentiments,
      keywords: keywordsFromText(filters.keywordsText),
      tagMode: filters.tagMode,
      limit: 100,
    }),
    [filters]
  );

  const loadFeed = useCallback(async (nextFilters) => {
    setLoading(true);
    setError("");
    try {
      const [tags, dash, arts] = await Promise.all([
        api.tags(),
        api.dashboard(nextFilters),
        api.articles(nextFilters),
      ]);
      setTagsMeta(tags);
      setDashboard(dash);
      setArticles(arts);
    } catch (err) {
      log.error("load feed failed", err);
      setError(err.message || "Failed to load feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const prefs = await api.preferences();
        const initial = {
          tags: prefs.tags || [],
          sentiments: prefs.sentiments?.length ? prefs.sentiments : ALL_SENTIMENTS,
          keywordsText: (prefs.keywords || []).join(", "),
          tagMode: prefs.tag_mode || "union",
        };
        setFilters(initial);
        await loadFeed({
          tags: initial.tags,
          sentiments: initial.sentiments,
          keywords: keywordsFromText(initial.keywordsText),
          tagMode: initial.tagMode,
          limit: 100,
        });
      } catch (err) {
        log.error("preferences load failed", err);
        setError(err.message);
        await loadFeed({
          tags: [],
          sentiments: ALL_SENTIMENTS,
          keywords: [],
          tagMode: "union",
          limit: 100,
        });
      } finally {
        setReady(true);
      }
    })();
  }, [loadFeed]);

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => loadFeed(queryFilters), 280);
    return () => clearTimeout(timer);
  }, [queryFilters, ready, loadFeed]);

  useEffect(() => {
    const id = setInterval(() => loadFeed(queryFilters), 60_000);
    return () => clearInterval(id);
  }, [loadFeed, queryFilters]);

  function persistable() {
    return {
      tags: filters.tags,
      sentiments: filters.sentiments,
      keywords: keywordsFromText(filters.keywordsText),
      tag_mode: filters.tagMode,
    };
  }

  async function handleSave() {
    setLoading(true);
    log.info("activity save priorities", persistable());
    try {
      await api.savePreferences(persistable());
      await loadFeed(queryFilters);
    } catch (err) {
      log.error("save priorities failed", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAgent(message) {
    setLoading(true);
    log.info("activity agent filter", message);
    try {
      const result = await api.agentFilter(message, true);
      const next = {
        tags: result.tags || [],
        sentiments: result.sentiments?.length ? result.sentiments : ALL_SENTIMENTS,
        keywordsText: (result.keywords || []).join(", "),
        tagMode: result.tag_mode || "union",
      };
      setFilters(next);
      setAgentNote(result.explanation);
      await loadFeed({
        tags: next.tags,
        sentiments: next.sentiments,
        keywords: keywordsFromText(next.keywordsText),
        tagMode: next.tagMode,
        limit: 100,
      });
    } catch (err) {
      log.error("agent filter failed", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleFetch() {
    setLoading(true);
    log.info("activity fetch this hour");
    try {
      await api.fetchNow();
      await loadFeed(queryFilters);
    } catch (err) {
      log.error("fetch now failed", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const sources = new Set(articles.map((a) => a.source_name).filter(Boolean)).size;

  return (
    <div className="shell" data-testid="app-shell">
      <Sidebar
        tagsMeta={tagsMeta}
        filters={filters}
        onChange={(next) => {
          setFilters(next);
        }}
        onSave={handleSave}
        onAgent={handleAgent}
        onFetch={handleFetch}
        agentNote={agentNote}
        loading={loading}
      />
      <main className="edition" data-testid="edition">
        <header className="edition-head">
          <div>
            <p className="kicker">Personal edition</p>
            <h2>Stories matching your desk</h2>
          </div>
          <div className="edition-actions">
            <button
              type="button"
              className="btn"
              data-testid="open-chat"
              onClick={() => window.dispatchEvent(new Event("newspulse-open-chat"))}
            >
              Ask the desk
            </button>
            <button
              type="button"
              className="btn"
              data-testid="refresh-filters"
              onClick={() => loadFeed(queryFilters)}
              disabled={loading}
            >
              Refresh filters
            </button>
          </div>
        </header>

        {error ? <div className="banner err" data-testid="error-banner">{error}</div> : null}

        <StatsBar
          dashboard={dashboard}
          articleCount={articles.length}
          sourceCount={sources}
          windowLabel={formatWindow(dashboard?.window_from, dashboard?.window_to)}
        />

        {articles.length === 0 ? (
          <p className="empty" data-testid="empty-state">
            No matching stories this hour. Widen tags, clear keywords, or fetch again.
          </p>
        ) : (
          <div className="story-grid" data-testid="story-grid">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        )}
      </main>
      <ChatBubble filters={queryFilters} />
    </div>
  );
}
