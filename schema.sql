
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO $$ BEGIN
    CREATE TYPE file_type_enum AS ENUM (
        'pdf',
        'csv',
        'txt',
        'docx',
        'image',
        'audio',
        'video',
        'website'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
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

CREATE TABLE IF NOT EXISTS contents (
    id          BIGSERIAL       PRIMARY KEY,
    content_id  VARCHAR(255)    UNIQUE NOT NULL,
    name        TEXT            NOT NULL,
    file_type   file_type_enum  NOT NULL DEFAULT 'pdf',
    file_size   BIGINT          CHECK (file_size >= 0),     -- bytes; NULL if unknown
    chunks      INTEGER         NOT NULL DEFAULT 0 CHECK (chunks >= 0),
    inserted_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ                                  -- soft delete
);

CREATE TABLE IF NOT EXISTS feeds (
    id          BIGSERIAL       PRIMARY KEY,
    feed_id     VARCHAR(255)    UNIQUE NOT NULL,
    url         TEXT            NOT NULL,
    chunks      INTEGER         NOT NULL DEFAULT 0 CHECK (chunks >= 0),
    inserted_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),      -- last re-crawl timestamp
    deleted_at  TIMESTAMPTZ                                  -- soft delete
);

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
    ON users(username);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
    ON users(email)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_active
    ON users(user_id)
    WHERE is_active = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_contents_content_id
    ON contents(content_id);

CREATE INDEX IF NOT EXISTS idx_contents_file_type
    ON contents(file_type);

CREATE INDEX IF NOT EXISTS idx_contents_active
    ON contents(content_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_contents_file_type_active
    ON contents(file_type)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_feeds_feed_id
    ON feeds(feed_id);

CREATE INDEX IF NOT EXISTS idx_feeds_active
    ON feeds(feed_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_feeds_updated_at_active
    ON feeds(updated_at ASC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_user_mappings_user_id
    ON user_mappings(user_id);

CREATE INDEX IF NOT EXISTS idx_user_mappings_content_id
    ON user_mappings(content_id)
    WHERE content_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_mappings_feed_id
    ON user_mappings(feed_id)
    WHERE feed_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mappings_user_content_uniq
    ON user_mappings(user_id, content_id)
    WHERE content_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mappings_user_feed_uniq
    ON user_mappings(user_id, feed_id)
    WHERE feed_id IS NOT NULL;
