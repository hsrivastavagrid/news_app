import { log } from "./logger.js";

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const started = performance.now();
  log.info("api request", method, path);
  try {
    const resp = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const ms = Math.round(performance.now() - started);
    if (!resp.ok) {
      let detail = "";
      try {
        detail = await resp.text();
      } catch {
        detail = "";
      }
      log.error("api error", method, path, "status=", resp.status, "ms=", ms, detail.slice(0, 300));
      throw new Error(`${resp.status} ${resp.statusText}`);
    }
    log.info("api ok", method, path, "status=", resp.status, "ms=", ms);
    return resp.json();
  } catch (err) {
    const ms = Math.round(performance.now() - started);
    log.error("api failed", method, path, "ms=", ms, err);
    throw err;
  }
}

function toCsv(list) {
  return (list || []).filter(Boolean).join(",");
}

export function buildQuery({ tags, sentiments, keywords, tagMode, limit = 100 }) {
  const params = new URLSearchParams();
  if (tags?.length) params.set("tags", toCsv(tags));
  if (sentiments?.length) params.set("sentiments", toCsv(sentiments));
  if (keywords?.length) params.set("keywords", keywords.join(","));
  if (tagMode) params.set("tag_mode", tagMode);
  params.set("limit", String(limit));
  return params.toString();
}

export const api = {
  tags: () => request("/api/tags"),
  dashboard: (filters) => request(`/api/dashboard?${buildQuery(filters)}`),
  articles: (filters) => request(`/api/articles?${buildQuery(filters)}`),
  contagion: () => request("/api/contagion"),
  preferences: () => request("/api/preferences"),
  savePreferences: (body) =>
    request("/api/preferences", { method: "PUT", body: JSON.stringify(body) }),
  agentFilter: (message, persist = true) =>
    request("/api/agent/filter", {
      method: "POST",
      body: JSON.stringify({ message, persist }),
    }),
  fetchNow: () => request("/api/fetch-now", { method: "POST" }),
};
