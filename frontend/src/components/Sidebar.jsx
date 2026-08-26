/**
 * Sidebar filter desk — adapted from Tejeswar001/news-dash NewsFilters
 * (topic selector + keyword search + preferred topics), moved into a
 * dedicated sidebar <select multiple> as required.
 */
const SENTIMENTS = [
  { id: "good", label: "Good" },
  { id: "bad", label: "Bad" },
  { id: "ugly", label: "Ugly" },
  { id: "neutral", label: "Neutral" },
];

export default function Sidebar({
  tagsMeta,
  filters,
  onChange,
  onSave,
  onAgent,
  onFetch,
  agentNote,
  loading,
}) {
  const selected = new Set(filters.tags);

  function toggleTagFromSelect(event) {
    const next = Array.from(event.target.selectedOptions).map((o) => o.value);
    onChange({ ...filters, tags: next });
  }

  function toggleSentiment(id) {
    const set = new Set(filters.sentiments);
    if (set.has(id)) set.delete(id);
    else set.add(id);
    onChange({ ...filters, sentiments: Array.from(set) });
  }

  function submitAgent(e) {
    e.preventDefault();
    const text = e.target.elements.priority.value.trim();
    if (text) onAgent(text);
  }

  return (
    <aside className="desk" data-testid="sidebar">
      <div className="masthead-mark">
        <span className="kicker">Hourly wire</span>
        <h1 data-testid="brand">NewsPulse</h1>
        <p>Personalised desk. Fetch wide, filter to your priorities.</p>
      </div>

      <section className="desk-block">
        <label htmlFor="tag-selector">Domain tags</label>
        <select
          id="tag-selector"
          data-testid="tag-selector"
          className="tag-selector"
          multiple
          size={8}
          value={filters.tags}
          onChange={toggleTagFromSelect}
        >
          {(tagsMeta || []).map((t) => (
            <option key={t.tag} value={t.tag}>
              {t.label} · {t.article_count} · {t.dominant_mode}
            </option>
          ))}
        </select>
        <p className="hint">
          Hold ⌘/Ctrl to multi-select. Empty = all domains. Matching is union
          (any selected tag) unless the agent sets intersection.
        </p>
        <div className="selected-row" data-testid="selected-tags">
          {filters.tags.length === 0 ? (
            <span className="chip ghost">All domains</span>
          ) : (
            filters.tags.map((tag) => (
              <span key={tag} className={`chip ${selected.has(tag) ? "on" : ""}`} data-testid={`tag-chip-${tag}`}>
                {tag}
              </span>
            ))
          )}
        </div>
      </section>

      <section className="desk-block">
        <span className="label">Sentiment</span>
        <div className="sent-grid">
          {SENTIMENTS.map((s) => (
            <label key={s.id} className={`sent-pill ${s.id}`} data-testid={`sentiment-${s.id}`}>
              <input
                type="checkbox"
                data-testid={`sentiment-check-${s.id}`}
                checked={filters.sentiments.includes(s.id)}
                onChange={() => toggleSentiment(s.id)}
              />
              {s.label}
            </label>
          ))}
        </div>
      </section>

      <section className="desk-block">
        <label htmlFor="keywords">Keywords</label>
        <input
          id="keywords"
          data-testid="keywords-input"
          type="text"
          placeholder="AI, rates, election…"
          value={filters.keywordsText}
          onChange={(e) => onChange({ ...filters, keywordsText: e.target.value })}
        />
      </section>

      <section className="desk-block">
        <label htmlFor="priority">Agent filter</label>
        <form onSubmit={submitAgent}>
          <textarea
            id="priority"
            name="priority"
            data-testid="agent-input"
            rows={4}
            placeholder='e.g. “Tech and finance, skip ugly, keywords AI and Fed”'
          />
          <button type="submit" className="btn ink" data-testid="agent-submit" disabled={loading}>
            Apply with agent
          </button>
        </form>
        {agentNote ? <p className="agent-note" data-testid="agent-note">{agentNote}</p> : null}
      </section>

      <div className="desk-actions">
        <button type="button" className="btn" data-testid="save-priorities" onClick={onSave} disabled={loading}>
          Save priorities
        </button>
        <button type="button" className="btn accent" data-testid="fetch-now" onClick={onFetch} disabled={loading}>
          {loading ? "Working…" : "Fetch this hour"}
        </button>
      </div>
    </aside>
  );
}
