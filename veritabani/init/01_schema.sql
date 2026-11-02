CREATE EXTENSION IF NOT EXISTS vector;

-- Kullanıcılar (kimlik doğrulama: Taha)
CREATE TABLE users (
  user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Standart kataloğu (aynı standardın revizyonları ayrı satır)
CREATE TABLE standards (
  standard_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code             TEXT NOT NULL,
  title            TEXT NOT NULL,
  version          TEXT NOT NULL,
  issuing_body     TEXT,
  publication_year INT,
  language         TEXT NOT NULL DEFAULT 'en',
  pdf_path         TEXT,
  status           TEXT NOT NULL DEFAULT 'ACTIVE'
                   CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'WITHDRAWN')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (code, version)
);

-- Standartların madde parçaları (RAG: Sudenur)
CREATE TABLE document_chunks (
  chunk_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  standard_id    BIGINT NOT NULL REFERENCES standards(standard_id) ON DELETE CASCADE,
  chunk_index    INT NOT NULL,
  section_number TEXT,
  clause_number  TEXT,
  page_number    INT,
  content        TEXT NOT NULL,
  embedding      vector(384),
  search_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  UNIQUE (standard_id, chunk_index)
);
CREATE INDEX idx_chunks_standard  ON document_chunks (standard_id);
CREATE INDEX idx_chunks_tsv       ON document_chunks USING GIN (search_tsv);
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Sohbet oturumları ve mesajlar
CREATE TABLE chat_sessions (
  session_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  title      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_user ON chat_sessions (user_id, created_at DESC);

CREATE TABLE messages (
  message_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id  BIGINT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'assistant')),
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_session ON messages (session_id, created_at);

-- Bir cevabın dayandığı kaynaklar (uygulamada "Kaynak" kartları)
CREATE TABLE message_references (
  reference_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  message_id    BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
  chunk_id      BIGINT REFERENCES document_chunks(chunk_id) ON DELETE SET NULL,
  standard_id   BIGINT REFERENCES standards(standard_id) ON DELETE SET NULL,
  clause_number TEXT,
  page_number   INT,
  source_url    TEXT,
  score         REAL
);
CREATE INDEX idx_refs_message ON message_references (message_id);

-- Kullanıcının kaydettiği standartlar
CREATE TABLE saved_standards (
  user_id     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  standard_id BIGINT NOT NULL REFERENCES standards(standard_id) ON DELETE CASCADE,
  saved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, standard_id)
);
