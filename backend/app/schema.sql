-- AeroStd Asistan — PostgreSQL şeması
-- Uygulama her açılışta bu dosyayı çalıştırır; tüm ifadeler tekrar çalıştırılabilir (idempotent).
-- {dim} yer tutucusu embedding boyutuyla (varsayılan 768) değiştirilir.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Kullanıcılar ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    username        TEXT,
    full_name       TEXT NOT NULL DEFAULT '',
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    organization    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Standart dokümanları ----------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL,                 -- ör. "MIL-STD-882E", "AC 20-115D"
    title           TEXT NOT NULL,
    issuer          TEXT NOT NULL DEFAULT '',      -- FAA, DoD, SHGM, EASA ...
    category        TEXT NOT NULL DEFAULT 'civil' CHECK (category IN ('civil', 'defense')),
    domains         TEXT[] NOT NULL DEFAULT '{}',  -- software, hardware, systems, safety ...
    language        TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'tr')),
    version         TEXT NOT NULL DEFAULT '',
    published_on    TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    file_name       TEXT NOT NULL,
    file_sha256     TEXT NOT NULL,
    page_count      INT NOT NULL DEFAULT 0,
    chunk_count     INT NOT NULL DEFAULT 0,
    embedded_count  INT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'parsing', 'embedding', 'ready', 'lexical_only', 'failed')),
    error           TEXT,
    uploaded_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_sha_uq ON documents (file_sha256);
CREATE INDEX IF NOT EXISTS documents_code_trgm ON documents USING gin (code gin_trgm_ops);

-- Madde (clause) bazlı parçalar -------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ord             INT NOT NULL,                  -- doküman içindeki sıra
    clause_ref      TEXT NOT NULL DEFAULT '',      -- ör. "4.3.2", "MADDE 12", "145.A.30"
    heading         TEXT NOT NULL DEFAULT '',      -- maddenin başlığı
    heading_path    TEXT NOT NULL DEFAULT '',      -- "4 GENERAL REQUIREMENTS › 4.3 ..."
    part            INT NOT NULL DEFAULT 1,        -- uzun maddeler bölündüyse parça no
    page_start      INT NOT NULL,
    page_end        INT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INT NOT NULL DEFAULT 0,
    tsv             TSVECTOR NOT NULL,
    embedding       VECTOR({dim})
);
CREATE INDEX IF NOT EXISTS chunks_doc_ord ON chunks (document_id, ord);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_clause_trgm ON chunks USING gin (clause_ref gin_trgm_ops);

-- Projeler (kullanıcı proje profilleri) ----------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT 'civil' CHECK (category IN ('civil', 'defense', 'both')),
    domains         TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS projects_user ON projects (user_id);

-- Kaydedilen standartlar / maddeler --------------------------------------
CREATE TABLE IF NOT EXISTS saved_items (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id        BIGINT REFERENCES chunks(id) ON DELETE CASCADE,
    project_id      BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    note            TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_uq
    ON saved_items (user_id, document_id, chunk_id) NULLS NOT DISTINCT;

-- Sohbet geçmişi ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    title           TEXT NOT NULL DEFAULT 'Yeni sohbet',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_user ON conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    citations       JSONB NOT NULL DEFAULT '[]'::jsonb,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages (conversation_id, id);

-- Sonradan eklenen sütunlar (eski veritabanlarında da güvenle çalışır)
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS users_username_uq ON users (lower(username));
ALTER TABLE messages ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS messages_saved ON messages (saved_at) WHERE saved_at IS NOT NULL;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS starred_at TIMESTAMPTZ;
