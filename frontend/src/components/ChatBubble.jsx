import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { log } from "../logger.js";

const STARTERS = [
  "What is the desk mood this hour?",
  "Which stories are ugly, with citations?",
  "Summarize tech coverage from the feed.",
];

function renderAnswer(text) {
  const parts = String(text || "").split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      return (
        <sup key={i} className="cite-mark">
          [{m[1]}]
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function ChatBubble({ filters }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Wire desk here. I only answer from this hour’s dashboard and fetched articles, with mandatory citations.",
      citations: [],
    },
  ]);
  const scroller = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, thinking, open]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 220);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    const openChat = () => setOpen(true);
    window.addEventListener("newspulse-open-chat", openChat);
    return () => window.removeEventListener("newspulse-open-chat", openChat);
  }, []);

  async function send(text) {
    const q = (text || input).trim();
    if (!q || thinking) return;
    setInput("");
    setError("");
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: q, citations: [] }]);
    setThinking(true);
    try {
      const result = await api.chat({
        message: q,
        history,
        tags: filters.tags || [],
        sentiments: filters.sentiments || [],
        keywords: filters.keywords || [],
        tag_mode: filters.tagMode || "union",
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer || "",
          citations: result.citations || [],
        },
      ]);
    } catch (err) {
      log.error("chat failed", err);
      setError(err.message || "Chat failed");
    } finally {
      setThinking(false);
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className={`chat-dock ${open ? "is-open" : ""}`}>
      <div className={`chat-panel ${open ? "is-open" : ""}`} data-testid="chat-panel" aria-hidden={!open}>
        <header className="chat-head">
          <div>
            <p className="kicker">Desk correspondent</p>
            <h3>Wire chat</h3>
          </div>
          <div className="chat-head-actions">
            <button
              type="button"
              className="btn btn-sm"
              onClick={() =>
                setMessages([
                  {
                    role: "assistant",
                    content: "Thread cleared. Ask about this hour’s desk — I will cite the feed.",
                    citations: [],
                  },
                ])
              }
            >
              Clear
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setOpen(false)} aria-label="Close chat">
              Close
            </button>
          </div>
        </header>

        <div className="chat-scroll" ref={scroller}>
          {messages.map((m, idx) => (
            <article key={idx} className={`chat-bubble ${m.role}`}>
              <p className="chat-copy">{m.role === "assistant" ? renderAnswer(m.content) : m.content}</p>
              {m.citations?.length ? (
                <ol className="chat-cites">
                  {m.citations.map((c) => (
                    <li key={c.id}>
                      <span className="cite-id">[{c.id}]</span>
                      {c.url ? (
                        <a href={c.url} target="_blank" rel="noopener noreferrer">
                          {c.title}
                        </a>
                      ) : (
                        <span>{c.title}</span>
                      )}
                      <em>
                        {c.source_name} · {c.sentiment_label}
                      </em>
                    </li>
                  ))}
                </ol>
              ) : null}
            </article>
          ))}
          {thinking ? (
            <article className="chat-bubble assistant thinking" data-testid="chat-thinking">
              <div className="think-row">
                <span className="think-nib" />
                <span className="think-nib" />
                <span className="think-nib" />
              </div>
              <p className="think-caption">Reading the wire… citing the desk</p>
            </article>
          ) : null}
          {error ? <p className="chat-error">{error}</p> : null}
          <div ref={endRef} />
        </div>

        {!messages.some((m) => m.role === "user") ? (
          <div className="chat-starters">
            {STARTERS.map((s) => (
              <button key={s} type="button" className="starter" disabled={thinking} onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        ) : null}

        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask the desk — answers cite fetched stories"
            disabled={thinking}
            data-testid="chat-input"
          />
          <button type="submit" className="btn ink" disabled={thinking || !input.trim()}>
            Send
          </button>
        </form>
      </div>

      <button
        type="button"
        className={`chat-fab ${open ? "is-open" : ""}`}
        data-testid="chat-fab"
        aria-label={open ? "Hide wire chat" : "Open wire chat"}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="fab-pulse" />
        {open ? "×" : "Ask desk"}
      </button>
    </div>
  );
}
