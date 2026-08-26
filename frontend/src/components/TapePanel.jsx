const SIGNAL_LABEL = {
  risk_off: "Risk-off",
  risk_on: "Risk-on",
  watch: "Watch",
};

export default function TapePanel({ tape, onSelectTicker }) {
  const names = tape?.names || [];

  return (
    <section className="tape" data-testid="tape">
      <header className="tape-head">
        <div>
          <p className="kicker">Trader tape</p>
          <h3>Names in this hour</h3>
        </div>
        <p className="tape-counts">
          <strong data-testid="tape-name-count">{tape?.name_count ?? 0}</strong> issuers
          <span className="mood bad"> · {tape?.risk_off_count ?? 0} risk-off</span>
          <span className="mood good"> · {tape?.risk_on_count ?? 0} risk-on</span>
        </p>
      </header>
      {names.length === 0 ? (
        <p className="tape-empty" data-testid="tape-empty">
          No named issuers in the matching stories. Fetch this hour or widen filters — the
          tape maps headlines to tickers, events, and risk-on/off flags.
        </p>
      ) : (
        <ol className="tape-list">
          {names.map((n) => (
            <li key={n.ticker} className={`tape-row signal-${n.signal}`}>
              <button
                type="button"
                className="tape-ticker"
                data-testid={`tape-ticker-${n.ticker}`}
                onClick={() => onSelectTicker?.(n.ticker, n.name)}
              >
                {n.ticker}
              </button>
              <div className="tape-meta">
                <strong>{n.name}</strong>
                <span className="tape-sector">{n.sector}</span>
                <span className={`mode-badge ${n.signal === "risk_off" ? "bad" : n.signal === "risk_on" ? "good" : "neutral"}`}>
                  {SIGNAL_LABEL[n.signal] || n.signal}
                </span>
                <span className="tape-event">{(n.event_types || []).join(" · ")}</span>
                <span className="tape-n">{n.article_count} stories</span>
              </div>
              <p className="tape-thesis">{n.thesis}</p>
              {n.headlines?.[0] ? <p className="tape-headline">{n.headlines[0]}</p> : null}
            </li>
          ))}
        </ol>
      )}
      <p className="tape-disclaimer">{tape?.disclaimer}</p>
    </section>
  );
}
