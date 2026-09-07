-- ═══════════════════════════════════════════════════════════════
--  ZymeRag / Axiom Gateway – Unified PostgreSQL / Supabase Schema
-- ═══════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ───────────────────────────────────────────────────────────────
--  ENUM TYPES
-- ───────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE file_type_enum AS ENUM (
        'pdf',
        'csv',
        'txt',
        'docx',
        'image',
        'audio',
        'video',
        'website',
        'policy'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ───────────────────────────────────────────────────────────────
--  1. USERS
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    user_id                  VARCHAR(255) PRIMARY KEY,
    username                 VARCHAR(255) NOT NULL UNIQUE,
    email                    VARCHAR(255) UNIQUE,
    password_hash            TEXT,
    refresh_token            TEXT,
    refresh_token_expires_at TIMESTAMPTZ,
    is_active                BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ───────────────────────────────────────────────────────────────
--  2. CONTENTS  (processed document metadata)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contents (
    id          BIGSERIAL       PRIMARY KEY,
    content_id  VARCHAR(255)    UNIQUE NOT NULL,
    name        TEXT            NOT NULL,
    file_type   file_type_enum  NOT NULL DEFAULT 'pdf',
    file_size   BIGINT          CHECK (file_size >= 0),
    chunks      INTEGER         NOT NULL DEFAULT 0 CHECK (chunks >= 0),
    inserted_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

-- ───────────────────────────────────────────────────────────────
--  3. FEEDS  (processed website / RSS feed metadata)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feeds (
    id          BIGSERIAL       PRIMARY KEY,
    feed_id     VARCHAR(255)    UNIQUE NOT NULL,
    url         TEXT            NOT NULL,
    chunks      INTEGER         NOT NULL DEFAULT 0 CHECK (chunks >= 0),
    inserted_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

-- ───────────────────────────────────────────────────────────────
--  4. USER_MAPPINGS  (user → content OR feed; never both, never neither)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_mappings (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    VARCHAR(255) NOT NULL REFERENCES users(user_id)       ON DELETE CASCADE,
    content_id VARCHAR(255)          REFERENCES contents(content_id) ON DELETE CASCADE,
    feed_id    VARCHAR(255)          REFERENCES feeds(feed_id)        ON DELETE CASCADE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_mapping_xor CHECK (
        (content_id IS NOT NULL AND feed_id IS NULL) OR
        (content_id IS NULL     AND feed_id IS NOT NULL)
    )
);

-- ───────────────────────────────────────────────────────────────
--  5. IDEMPOTENCY KEYS (Deduplication across restarts/workers)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    result_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ───────────────────────────────────────────────────────────────
--  6. POLICY CHUNKS (Relational metadata mirrored with FAISS vector index on disk)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(255) REFERENCES contents(content_id) ON DELETE CASCADE,
    section_heading TEXT,
    page_number INT,
    text TEXT NOT NULL,
    faiss_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_chunks_doc_id ON policy_chunks(doc_id);

-- ───────────────────────────────────────────────────────────────
--  7. EXTRACTED RULES (Offline LLM extracted, Human-approved, Deterministic runtime evaluated)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version INT NOT NULL DEFAULT 1,
    scope JSONB NOT NULL,
    condition JSONB NOT NULL,
    effect TEXT NOT NULL CHECK (effect IN ('ALLOW', 'BLOCK', 'ESCALATE')),
    required_approval_role TEXT,
    source_document VARCHAR(255) REFERENCES contents(content_id) ON DELETE SET NULL,
    source_chunk UUID REFERENCES policy_chunks(chunk_id) ON DELETE SET NULL,
    source_clause TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rules_status ON rules(status);
CREATE INDEX IF NOT EXISTS idx_rules_scope ON rules USING GIN (scope);

-- ───────────────────────────────────────────────────────────────
--  8. FLOW REGISTRY (Deterministic mapping of tool + operation -> flow_id)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS flow_registry (
    tool TEXT NOT NULL,
    operation TEXT NOT NULL,
    flow_id TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (tool, operation)
);

-- ───────────────────────────────────────────────────────────────
--  9. APPROVALS (Escalated actions requiring human approval with pre-execution revalidation)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id UUID NOT NULL,
    rule_id UUID REFERENCES rules(rule_id) ON DELETE SET NULL,
    action_payload JSONB NOT NULL,
    required_role TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_action_id ON approvals(action_id);

-- ───────────────────────────────────────────────────────────────
--  10. AUDIT EVENTS (Cryptographic SHA-256 Hash Chained for Tamper-Evidence)
-- ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id UUID NOT NULL,
    agent_id TEXT,
    user_id TEXT,
    tool TEXT,
    operation TEXT,
    flow_id TEXT,
    matched_rule_id UUID REFERENCES rules(rule_id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    details JSONB,
    prev_hash TEXT,
    curr_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_action_id ON audit_events(action_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);
