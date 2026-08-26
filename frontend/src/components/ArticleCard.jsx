/**
 * Article card layout adapted from Tejeswar001/news-dash NewsArticleCard:
 * image, source badge, timestamp, title, dek, actions.
 */
import { useState } from "react";

function isPublisherUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    if (host === "example.com" || host.endsWith(".example.com")) return false;
    if (host === "newsapi.org") return false;
    if ((host === "news.google.com" || host === "www.news.google.com") && parsed.pathname.startsWith("/search")) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

function formatWhen(value) {
  if (!value) return "";
  const raw = String(value).replace(" ", "T");
  const dt = new Date(raw.endsWith("Z") || raw.includes("+") ? raw : `${raw}Z`);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ArticleCard({ article }) {
  const [imgFail, setImgFail] = useState(false);
  const showImg = article.image_url && !imgFail;
  const href = isPublisherUrl(article.url) ? article.url : null;

  return (
    <article className={`story sentiment-${article.sentiment_label}`} data-testid="article-card">
      {showImg ? (
        <div className="story-art">
          <img
            src={article.image_url}
            alt=""
            onError={() => setImgFail(true)}
          />
        </div>
      ) : null}
      <div className="story-body">
        <div className="story-meta">
          <span className="source">{article.source_name || "Wire"}</span>
          <span className={`mode-badge ${article.sentiment_label}`}>
            {article.sentiment_label}
          </span>
          <time>{formatWhen(article.published_at || article.fetched_at)}</time>
        </div>
        <h3>
          {href ? (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {article.title}
            </a>
          ) : (
            article.title
          )}
        </h3>
        {article.description ? <p className="dek">{article.description}</p> : null}
        <div className="story-tags">
          {(article.tags || []).map((t) => (
            <span key={t} className="chip">
              {t}
            </span>
          ))}
        </div>
        {href ? (
          <a className="read-full" data-testid="read-full" href={href} target="_blank" rel="noopener noreferrer">
            Read more
          </a>
        ) : (
          <span className="read-full" data-testid="read-full-unavailable">
            No publisher link
          </span>
        )}
      </div>
    </article>
  );
}
