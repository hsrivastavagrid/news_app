-- Core articles table
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source_name TEXT,
    api_category TEXT,
    url TEXT NOT NULL,
    image_url TEXT,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    compound_score REAL NOT NULL,
    positive_score REAL NOT NULL,
    negative_score REAL NOT NULL,
    neutral_score REAL NOT NULL,
    sentiment_label TEXT NOT NULL,
    ugly_keyword_count INTEGER DEFAULT 0
);

-- Junction table: many-to-many between articles and tags
CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (article_id, tag),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- Per-tag hourly aggregated snapshots
CREATE TABLE IF NOT EXISTS tag_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TIMESTAMP NOT NULL,
    tag TEXT NOT NULL,
    total_articles INTEGER,
    good_count INTEGER DEFAULT 0,
    bad_count INTEGER DEFAULT 0,
    ugly_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    avg_compound REAL,
    UNIQUE(snapshot_time, tag)
);

-- Cross-domain contagion events
CREATE TABLE IF NOT EXISTS contagion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_tag TEXT NOT NULL,
    target_tag TEXT NOT NULL,
    severity TEXT DEFAULT 'moderate',
    source_compound_delta REAL,
    target_compound_current REAL,
    message TEXT,
    resolved BOOLEAN DEFAULT 0
);

-- Single-user personalization (priority tags, sentiments, keywords)
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tags TEXT NOT NULL DEFAULT '[]',
    sentiments TEXT NOT NULL DEFAULT '["good","bad","ugly","neutral"]',
    keywords TEXT NOT NULL DEFAULT '[]',
    tag_mode TEXT NOT NULL DEFAULT 'union',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO user_preferences (id) VALUES (1);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag);
CREATE INDEX IF NOT EXISTS idx_article_tags_article ON article_tags(article_id);
CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_snapshots_tag_time ON tag_snapshots(tag, snapshot_time);
CREATE INDEX IF NOT EXISTS idx_contagion_time ON contagion_events(detected_at);
