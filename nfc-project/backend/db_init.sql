CREATE TABLE IF NOT EXISTS mappings (
    uid TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    name TEXT,
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mappings_updated_at ON mappings(updated_at DESC);
