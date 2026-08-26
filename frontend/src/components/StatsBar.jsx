/** Stats row adapted from Tejeswar001/news-dash dashboard KPI cards. */

export default function StatsBar({ dashboard, articleCount, sourceCount, windowLabel }) {
  const d = dashboard || {};
  const total = d.total_articles || 0;
  const uglyPct = total ? Math.round((d.ugly_count / total) * 100) : 0;

  return (
    <section className="stats" data-testid="stats">
      <div className="stat">
        <span className="stat-kicker">This hour</span>
        <strong data-testid="stat-window">{windowLabel || "rolling 60 min"}</strong>
      </div>
      <div className="stat">
        <span className="stat-kicker">Matching stories</span>
        <strong data-testid="stat-stories">{articleCount}</strong>
      </div>
      <div className="stat">
        <span className="stat-kicker">Sources</span>
        <strong>{sourceCount}</strong>
      </div>
      <div className="stat">
        <span className="stat-kicker">Desk mood</span>
        <strong className={`mood ${d.dominant_mode || "neutral"}`}>
          {(d.dominant_mode || "neutral").toUpperCase()}
        </strong>
      </div>
      <div className="stat">
        <span className="stat-kicker">Ugly index</span>
        <strong>{uglyPct}%</strong>
      </div>
    </section>
  );
}
