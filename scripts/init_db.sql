-- ============================================
-- Echorouk AI Swarm — Database Initialization
-- ============================================
-- This script runs automatically on first PostgreSQL startup.
-- It creates the pgvector extension and sets up initial config.

-- Enable pgvector for future embeddings (RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- Table: Users (Echorouk Editorial Team)
-- ============================================

CREATE TYPE user_role AS ENUM ('director', 'editor_chief', 'journalist', 'social_media', 'print_editor');

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    full_name_ar    VARCHAR(100)  NOT NULL,
    username        VARCHAR(50)   UNIQUE NOT NULL,
    hashed_password VARCHAR(255)  NOT NULL,
    role            user_role     NOT NULL DEFAULT 'journalist',
    departments     TEXT[]        NOT NULL DEFAULT '{}',
    specialization  VARCHAR(200),
    is_active       BOOLEAN       DEFAULT TRUE,
    is_online       BOOLEAN       DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- ============================================
-- Seed: Default RSS Sources (Algeria-focused)
-- ============================================

CREATE TABLE IF NOT EXISTS sources (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(255) NOT NULL,
    slug                    VARCHAR(255),
    method                  VARCHAR(20)  NOT NULL DEFAULT 'rss',
    url                     VARCHAR(1024) NOT NULL UNIQUE,
    rss_url                 VARCHAR(1024),
    category                VARCHAR(100) DEFAULT 'general',
    language                VARCHAR(10)  DEFAULT 'ar',
    languages               VARCHAR(50),
    region                  VARCHAR(50),
    source_type             VARCHAR(50),
    description             TEXT,
    trust_score             FLOAT DEFAULT 0.5,
    credibility             VARCHAR(20) DEFAULT 'medium',
    priority                INTEGER DEFAULT 5,
    enabled                 BOOLEAN DEFAULT TRUE,
    fetch_interval_minutes  INTEGER DEFAULT 30,
    last_fetched_at          TIMESTAMP,
    error_count             INTEGER DEFAULT 0,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_sources_slug
    ON sources (slug)
    WHERE slug IS NOT NULL;

INSERT INTO sources (name, url, category, language, trust_score, priority, enabled, fetch_interval_minutes) VALUES
-- Official Algerian Sources
('وكالة الأنباء الجزائرية (APS)', 'https://www.aps.dz/xml/rss', 'official', 'ar', 1.0, 10, true, 15),

-- Algerian Media
('الشروق أونلاين', 'https://www.echoroukonline.com/feed/', 'media_dz', 'ar', 0.9, 9, true, 30),
('الخبر', 'https://www.elkhabar.com/feed/', 'media_dz', 'ar', 0.85, 8, true, 30),
('النهار أونلاين', 'https://www.ennaharonline.com/feed/', 'media_dz', 'ar', 0.80, 7, true, 30),
('TSA Algérie', 'https://www.tsa-algerie.com/feed/', 'media_dz', 'fr', 0.85, 8, true, 30),
('Algérie 360', 'https://www.algerie360.com/feed/', 'media_dz', 'fr', 0.80, 6, true, 60),
('Express DZ', 'https://www.expressdz.dz/feed/', 'media_dz', 'fr', 0.75, 5, true, 60),
('Le Matin d''Algérie', 'https://lematindalgerie.com/feed/', 'media_dz', 'fr', 0.80, 6, true, 60),
('ObservAlgérie', 'https://observalgerie.com/feed/', 'media_dz', 'fr', 0.75, 5, true, 60),
('El Watan', 'https://feeds.feedburner.com/elwatan/4pwdGeU2mTa', 'media_dz', 'fr', 0.85, 7, true, 60),

-- International Sources (Algeria section)
('France 24 Algérie', 'https://www.france24.com/fr/tag/alg%C3%A9rie/rss', 'international', 'fr', 0.90, 7, true, 60),
('RFI Algérie', 'https://www.rfi.fr/fr/tag/alg%C3%A9rie/rss', 'international', 'fr', 0.90, 7, true, 60),
('Le Monde Algérie', 'https://www.lemonde.fr/algerie/rss_full.xml', 'international', 'fr', 0.95, 6, true, 60),
('BFM TV Algérie', 'https://www.bfmtv.com/rss/international/afrique/algerie/', 'international', 'fr', 0.85, 5, true, 60),
('EURO News Français', 'https://fr.euronews.com/rss', 'international', 'fr', 0.85, 4, true, 60),
('Google News Algérie', 'https://news.google.com/rss/search?tbm=nws&q=Alg%E9rie&hl=fr&gl=FR&ceid=FR:fr', 'aggregator', 'fr', 0.70, 5, true, 30),
('Flipboard Algérie', 'https://flipboard.com/topic/fr-alg%C3%A9rie.rss', 'aggregator', 'fr', 0.65, 4, true, 60),

-- Sports
('Express DZ Sport', 'https://www.expressdz.dz/category/sport/feed/', 'sports', 'fr', 0.75, 5, true, 60),
('TSA Sport', 'https://www.tsa-algerie.com/category/sport/feed/', 'sports', 'fr', 0.80, 6, true, 60),

-- Economy
('Express DZ Économie', 'https://www.expressdz.dz/category/economie/feed/', 'economy', 'fr', 0.75, 5, true, 60),
('TSA Économie', 'https://www.tsa-algerie.com/category/economie/feed/', 'economy', 'fr', 0.80, 6, true, 60),

-- Culture
('Express DZ Culture', 'https://www.expressdz.dz/category/culture/feed/', 'culture', 'fr', 0.75, 4, true, 60),
('Tamazgha', 'https://tamazgha.fr/spip.php?page=backend', 'culture', 'fr', 0.70, 4, true, 60),
('Kabyle.com', 'https://kabyle.com/feed', 'culture', 'fr', 0.70, 4, true, 60),

-- Academic / Analysis
('The Conversation Algérie', 'https://theconversation.com/topics/algerie-25902/articles.atom', 'analysis', 'fr', 0.90, 5, true, 120)
ON CONFLICT (url) DO NOTHING;
