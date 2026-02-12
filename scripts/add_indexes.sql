-- Minimal performance indexes for Echorouk AI Swarm

-- 1) Fast text search on titles
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_articles_original_title_trgm
ON articles USING gin (original_title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_articles_title_ar_trgm
ON articles USING gin (title_ar gin_trgm_ops);

-- 2) Common sort paths
CREATE INDEX IF NOT EXISTS ix_articles_published_at
ON articles (published_at DESC);

CREATE INDEX IF NOT EXISTS ix_articles_candidate_order
ON articles (status, importance_score DESC, crawled_at DESC);

-- 3) Editorial decisions lookup
CREATE INDEX IF NOT EXISTS ix_editor_decisions_article_id
ON editor_decisions (article_id);
