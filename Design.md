# ZymeRag — Design Document

This document describes the internal design of ZymeRag: the data model, the ingestion pipelines, the retrieval/answering pipeline, authentication, background jobs, and the trade‑offs and known issues in the current implementation. It is meant to complement `README.md`, which focuses on setup and usage.

---

## 1. Goals & Non‑Goals

**Goals**
- Ingest heterogeneous content (documents, images, audio, video, spreadsheets, websites) into a searchable knowledge base without requiring a dedicated vector database server.
- Provide hybrid retrieval (keyword + semantic) scoped to an arbitrary set of document/feed IDs per query, so a client can decide at query time which knowledge to search (e.g. "search only these 3 documents").
- Ground LLM answers in retrieved context, and optionally fall back to live web search when local knowledge is insufficient.
- Keep infrastructure minimal: Postgres for metadata, flat files + FAISS/BM25 pickles on local disk for vectors/keyword indexes, Redis for job scheduling/coordination.

**Non‑goals (at this stage)**
- Multi‑tenant sharding of vector indexes at scale (indexes are per‑document flat files, not a distributed vector DB).
- Real‑time collaborative editing or streaming ingestion progress to the client.
- Fine‑grained authorization beyond "is this a valid user" — the `user_mappings` table records ownership but most endpoints don't yet enforce it (see §9).

---

## 2. High‑Level Data Flow

### 2.1 Ingestion

```
Client upload (multipart) ──▶ Upload Controller (validates type/size, idempotency)
        │
        ▼
Doc-specific Ingestion module (DocsIngestion/* or WebsiteIngestion/*)
        │  1. Extract raw text
        │     - PDF/DOCX  → docling (markdown export) or PyMuPDF fallback
        │     - Image     → PaddleOCR (GPU/CPU) or pytesseract fallback
        │     - Audio     → faster-whisper transcription
        │     - Video     → ffmpeg extracts audio track → faster-whisper
        │     - CSV       → pandas, one Document per row ("col: value" lines)
        │     - Website   → crawl4ai crawl → pruned markdown
        │
        ▼
        2. Chunk the extracted text (Splitter/*)
        │     - Header-aware split (MarkdownHeaderTextSplitter) then
        │       recursive character split (RecursiveCharacterTextSplitter)
        │
        ▼
        3. Embed chunks (Embeddings/Embeddingmaker.py → Qwen3-Embedding-0.6B)
        │  and build a FAISS index; also build a BM25Okapi index over the raw
        │  chunk text and pickle it alongside the FAISS files
        │
        ▼
        4. Persist to disk under Data/Content/<uuid>/ or Data/Feed/<uuid>/
        │
        ▼
        5. Write metadata row to Postgres (contents/feeds table) via Dbhelper
        │
        ▼
Return the generated UUID to the client as the document's addressable ID
```

### 2.2 Query / Answering

```
GET /query/query?question=...&ids=id1&ids=id2 ...
        │
        ▼
Query Controller: validate question, build context
        │
        ▼
Query.DirectQuery.get_all_chunks(question, ids)
        │  runs concurrently (asyncio.gather):
        │    - BM25Query: load bm25.pkl per id, score, take top-k per id, merge+sort desc
        │    - SemanticQuery: FAISS.load_local per id, similarity_search_with_score, merge+sort asc
        │
        ▼
Concatenate BM25 results + semantic results into one chunk list
        │
        ▼
build_context(): join each chunk's page_content with blank lines
        │
        ▼
LLM.Llm.generate_answer(question, context)
        │  - fetches the currently "active" Groq API key from Redis
        │    (falls back to first key in GROQ_API_KEY if Redis is empty)
        │  - calls Groq chat completion with a context-constrained prompt
        │
        ▼
Return the generated answer text to the client
```

A parallel, more advanced path exists (`get_all_chunks_with_fallback` in `DirectQuery.py`) that evaluates whether the KB chunks are "sufficient" (via `WebSearchFallback.is_kb_sufficient`) and, if not, performs a Tavily/Exa web search and synthesizes an answer with `ChatGroq` (llama‑3.3‑70b‑versatile) instead. **This path is not currently invoked by `query_controller.py`** — see §9.

---

## 3. Module‑by‑Module Design

### 3.1 `Backend/` — API Layer

- **`app.py`** — creates the FastAPI app, adds a permissive CORS middleware (`allow_origins=["*"]`), registers the four routers under `/upload`, `/delete`, `/query`, `/user`, and mounts `static/` at `/static` plus serves `static/index.html` at `/` and `/ui`.
- **`Router/*`** — thin, declarative route registration (`add_api_route`) mapping HTTP verb + path to a controller function. No business logic lives here.
- **`Controller/*`** — the actual request handlers:
  - `upload_controller.py` — one function per file type (`upload_pdf`, `upload_docx`, `upload_image`, `upload_csv`, `upload_audio`, `upload_video`). Each:
    1. Acquires a process‑local `asyncio.Lock` to check/set an idempotency key.
    2. Validates `Content-Type` against an allow‑list.
    3. Validates file size ≤ 10 MB (except the PDF path, which currently skips this check).
    4. Delegates to the relevant ingestion module.
    5. Returns `{"message", "id"}` or raises `HTTPException`.
  - `delete_controller.py` — looks for a matching folder under `Data/Content/<id>` first, then `Data/Feed/<id>`; deletes the folder off‑thread (`asyncio.to_thread(shutil.rmtree, ...)`) and soft‑deletes the corresponding DB row.
  - `query_controller.py` — parses `question` + repeated `ids`, calls `DirectQuery.get_all_chunks`, builds a flat context string, and calls `LLM.generate_answer`.
  - `user_controller.py` — registration, access/refresh token issuance, refresh, logout (see §5).
- **`Middleware/auth.py`** — defines `verify_token()` (JWT decode + type check) and an `auth_middleware` HTTP middleware that reads `access_token` from a cookie or an `Authorization: Bearer` header and attaches `request.state.user_id`. *Design intent* is a global auth gate; *current wiring* only applies it as a per‑route `Depends()` on `refresh_access_token` (see §9 — inconsistent enforcement).
- **`Utils/Hash.py`** — Argon2 password hashing/verification via `argon2-cffi`.
- **`Utils/Rotater.py`** — a standalone worker (not imported by the API process) that rotates a round‑robin index over the comma‑separated `GROQ_API_KEY` env value every 5 minutes via a repeating BullMQ job, and writes the currently active key into Redis at `nori:groq_active_key`. `LLM/Llm.py` reads that key before every generation call, defaulting to the first configured key if Redis has nothing set.

### 3.2 `DocsIngestion/` — Per‑Type Extraction + Indexing

Each ingestion module follows the same shape: extract text → chunk → embed + FAISS → (optionally) BM25 → save metadata row → return a UUID.

- **`PdfIngestion.py`**
  - Prefers `docling`'s `DocumentConverter`/`DocumentStream` to convert PDF bytes to Markdown (preserves headings/structure for the header‑aware splitter); falls back to `pymupdf` plain text extraction if `docling` isn't installed.
  - Builds both a FAISS index (`FAISS.from_documents`) **and** a BM25 index (`BM25Okapi` over tokenized chunk text), pickling `{"documents": [...], "bm25": bm25}` to `bm25.pkl` — this is the only ingestion module (besides website ingestion) that persists a BM25 index, which is what makes BM25 retrieval work for PDFs/DOCX.
  - Also exposes `delete_content(id)` as a standalone helper (separate from `delete_controller.py`, which reimplements similar logic — mild duplication).
  - DOCX uploads are routed through this same `ingest_pdf()` function (docling can also parse DOCX streams).
- **`CsvIngestion.py`** — reads the CSV with pandas, and turns **each row** into a LangChain `Document` whose `page_content` is `"col: value"` lines and whose `metadata` is the row dict. Chunking is skipped (rows are already small); goes straight to FAISS.
- **`ImageIngestion.py`** — OCR‑first pipeline. Lazily initializes a PaddleOCR engine (GPU if `torch.cuda.is_available()`, else CPU); if PaddleOCR fails to import/initialize, silently falls back to `pytesseract`. Runs OCR off the event loop thread (`asyncio.to_thread`), then splits + embeds the recognized text like a normal document.
- **`AudioVideoIngestion.py`**
  - Lazily loads a `faster-whisper` `WhisperModel("medium")`, `float16` on CUDA / `int8` on CPU.
  - Audio path: write the uploaded bytes to a temp file, transcribe, clean up.
  - Video path: write to a temp file, use `ffmpeg-python` to extract a mono 16kHz WAV track, transcribe that, clean up both temp files.
- **`TextIngestion.py`** — a plain‑text ingestion helper (used for text content that doesn't come from a file upload, e.g. programmatic text ingestion). Skips chunking for short strings (≤300 chars) and wraps them in a single `Document`.

All of the above modules resolve `Data/Content/<uuid>` relative to the current working directory (`Path("Data").resolve()`), so **the backend must be started from a consistent working directory** for indexes to be found reliably across restarts.

### 3.3 `WebsiteIngestion/` — Crawling Pipeline

- Uses `crawl4ai`'s `AsyncWebCrawler` with a `CrawlerRunConfig` that strips `nav/footer/header/style/script` tags, removes overlays/consent popups, waits for `domcontentloaded`, and scans the full page.
- Applies a `PruningContentFilter` (threshold 0.5) + `DefaultMarkdownGenerator` to reduce boilerplate before markdown is produced (`result.markdown.fit_markdown`).
- `ingest_website(url)` — crawl → chunk (`WebsiteTextSplitter`) → build BM25 pickle → build FAISS index → save under `Data/Feed/<uuid>` → insert into `feeds` table.
- `update_website(url, id)` — re‑crawls and rebuilds the index **into a temporary sibling directory** (`Data/Feed/<id>__temp`), then atomically swaps it in (`rmtree` old, `rename` temp → final) so a query hitting the same feed mid‑refresh doesn't see a half‑written index. *Note: this atomic‑swap approach is not used for the BM25 pickle during updates* — `update_website` currently doesn't rebuild `bm25.pkl` at all, only the FAISS index (see §9).
- `delete_website(id)` — removes the feed's folder from disk (DB soft‑delete happens in `delete_controller.py`).

### 3.4 `Splitter/` — Chunking Strategy

Both `PdfTextSplitter` and `WebsiteTextSplitter` follow the same two‑stage approach:

1. **`MarkdownHeaderTextSplitter`** splits on `#`, `##`, `###`, `####` headers first (with `strip_headers=False`, so heading text stays attached to its section) — this keeps semantically related content grouped by document structure before any character‑level splitting happens.
2. **`RecursiveCharacterTextSplitter`** then splits each section further using a separator cascade (`\n\n`, `\n`, sentence punctuation, `; `, `, `, space, empty string), which prefers to break on paragraph/sentence boundaries before falling back to hard character cuts.

They differ only in target chunk size, tuned per source type:

| Splitter | `chunk_size` | `chunk_overlap` | Rationale |
|---|---|---|---|
| `PdfTextSplitter` | 300 chars | 80 chars | Smaller chunks for denser, fact‑heavy document text |
| `WebsiteTextSplitter` | 700 chars | 100 chars | Larger chunks since web content tends to be more prose‑like/verbose |

### 3.5 `Embeddings/Embeddingmaker.py`

A thin `langchain_core.embeddings.Embeddings` subclass wrapping a `sentence-transformers` model (`Qwen/Qwen3-Embedding-0.6B` by default). Embeddings are L2‑normalized (`normalize_embeddings=True`) and cast to `float32`, which makes inner‑product / cosine similarity behave consistently with FAISS's default index type. A single `Embedder` instance is created once per process and reused across all ingestion/query calls (model loading is expensive, so this amortizes startup cost).

### 3.6 `Query/` — Retrieval

- **`BM25Query.py`** — for each requested ID, loads that document's `bm25.pkl`, tokenizes the query (`\b\w+\b`, lowercased), scores all chunks, takes the top‑`k` (default 6) per ID, merges across IDs, and sorts **descending** by score (higher BM25 score = more relevant).
- **`SemanticQuery.py`** — for each requested ID, loads the FAISS index and runs `similarity_search_with_score`, merges across IDs, and sorts **ascending** by score (FAISS's default metric is a distance, so lower = more relevant) — note this is the opposite sort direction from BM25, which is correct for each individually but means the two result sets are **not on a comparable scale** once merged (see §9).
- **`WebSearchFallback.py`** — a self‑contained fallback component:
  - `search_tavily()` / `search_exa()` — call the respective search API and return `(context_text, source_urls)`.
  - `web_search_fallback()` — tries Tavily first, then Exa, returns `None` if neither is configured/succeeds.
  - `synthesize_answer()` — feeds the retrieved web context into a strict, citation‑oriented prompt (`WEB_SEARCH_PROMPT`) run through `ChatGroq` (`llama-3.3-70b-versatile`), explicitly instructed to answer only from the provided context, refuse to fabricate, detect and mirror the user's language, and cite sources by name.
  - `is_kb_sufficient()` — treats an empty chunk list as insufficient; otherwise looks at the max score across chunks and compares it to a `threshold` (default 0.5).
  - `evaluate_and_fallback()` — the orchestration entrypoint: returns the KB chunks untouched if sufficient, otherwise runs the web fallback and returns a synthesized answer instead.
- **`DirectQuery.py`** — the orchestrator used by the API:
  - `get_all_chunks(question, ids)` — runs BM25 and semantic retrieval concurrently and returns their concatenation.
  - `get_all_chunks_with_fallback(...)` — layers `WebSearchFallback.evaluate_and_fallback` on top. **Not currently wired into `query_controller.py`** (see §9).

### 3.7 `LLM/Llm.py`

- Maintains its own Redis client and reads the "active" Groq API key (as rotated by `Rotater.py`) before every call, falling back to the first key in `GROQ_API_KEY` if Redis has no value set — this means the LLM layer works even if the rotation worker isn't running.
- Builds a strict, context‑only prompt ("Answer the question using only the context below. If the answer isn't in the context, say so.") and calls Groq's chat completions API at `temperature=0.2` for low‑variance, mostly‑deterministic answers.

### 3.8 `Dbhelper/` — Persistence Layer

- **`config.py`** — loads `.env`, resolves `DATABASE_URL` (or `SUPABASE_DB_URL` as an alias), normalizes the `postgres://` scheme to `postgresql://`, and derives an async‑driver URL (`postgresql+asyncpg://`) for use with SQLAlchemy's async engine. Also ensures a local `Data/` directory exists.
- **`db.py`** — creates a pooled `AsyncEngine` (`pool_size=20`, `max_overflow=40`, `pool_recycle=300`, `pool_pre_ping=True`) and an `async_sessionmaker` (`AsyncDB`). Disables asyncpg's prepared‑statement caching (`statement_cache_size=0`) — this is the standard workaround needed when connecting through PgBouncer in transaction‑pooling mode (as Supabase's pooled connection strings typically require).
- **`models.py`** — SQLAlchemy declarative models (`UserModel`, `ContentModel`, `FeedModel`, `UserMappingModel`) mirroring `schema.sql`, plus plain `@dataclass` shapes (`User`, `ContentItem`, `FeedItem`, `UserMapping`) used as lightweight, ORM‑independent return types from the helper functions. A `FileType` enum (`pdf/csv/txt/docx/image/audio/video/website`) backs the Postgres `file_type_enum`.
- **`user_db_helper.py`** — a comprehensive CRUD surface over `users` and `user_mappings`:
  - User create/read (`by_id`/`by_username`/`by_email`), existence checks, listing, counting.
  - Profile updates (username/email/password hash).
  - Refresh‑token lifecycle: `update_refresh_token` (always stores a SHA‑256 hash, never the raw token), `verify_refresh_token` (constant‑time comparison via `hmac.compare_digest`, plus expiry check), `clear_refresh_token`.
  - Soft delete / reactivate (`is_active` flag) plus a `delete_user` hard‑delete that intentionally is **not** the recommended path (see its own docstring — mappings must be cleared first or the FK will reject the delete).
  - `link_user_to_content` / `link_user_to_feed` — idempotent inserts (`ON CONFLICT DO NOTHING`) recording which user owns which content/feed. These exist but are **not currently called from any controller** — ownership is modeled in the schema but not yet wired into the upload flow (see §9).
- **`pdf_db_helper.py`** — CRUD for the `contents` table: insert‑on‑ingest, update chunk count, fetch by ID, soft‑delete.
- **`website_db_helper.py`** — CRUD for the `feeds` table: insert‑on‑ingest, fetch all active URLs (used by the re‑crawl scheduler), update last‑crawled timestamp/chunk count, fetch by ID, soft‑delete.

Every helper function follows the same defensive pattern: open a session via the `AsyncDB()` context manager, run the query, commit, and catch both `SQLAlchemyError` and generic `Exception` separately (logging via `logger.exception` and returning a safe default — `False`, `None`, or `[]`) so a database hiccup surfaces as a clean failure rather than an unhandled 500 with a stack trace.

### 3.9 `Scheduler/BullMqScheduler.py`

A standalone worker process that:
1. Registers a **repeating** BullMQ job (`every: 24h`, up to 3 attempts with exponential backoff) on a queue named `"Chunks Updation"`.
2. Its `process()` callback fetches every non‑deleted feed's `(url, feed_id)` pair from Postgres and calls `WebsiteIngestion.update_website(url, id)` for each — refreshing the crawl and rebuilding the FAISS index in place (see §3.3's atomic‑swap note).
3. Runs forever (`await asyncio.Future()`), so it's meant to be started as its own OS‑level process/service, not imported into the API process.

### 3.10 Frontend Apps

- **`frontend/` (React 19 + Vite)** — a single‑page "API console" (`App.jsx`, ~1,240 lines) intended for developers/operators:
  - Configurable backend base URL with a health check against `/openapi.json`.
  - A file drop‑zone that auto‑maps file extensions to the correct upload endpoint (`EXT_MAP`), covering pdf/docx/images/csv‑xlsx/audio/video.
  - An endpoint picker grid so a user can override the auto‑detected endpoint.
  - A query panel that calls `/query/query` with a question and a list of IDs.
  - A delete panel that calls `/delete/delete_content`.
  - A filterable, timestamped request log (method, endpoint, status, duration, response) for observability while testing the API by hand.
- **`static/` (vanilla HTML/CSS/JS)** — served directly by FastAPI at `/` and `/ui`, no build tooling required; a simpler surface aimed at end users rather than API debugging.

---

## 4. Data Model

```
users
├── user_id (PK, text)
├── username (unique)
├── email (unique, nullable)
├── password_hash
├── refresh_token (hashed at rest)
├── refresh_token_expires_at
├── is_active
├── created_at / updated_at

contents                              feeds
├── id (PK, serial)                   ├── id (PK, serial)
├── content_id (unique)               ├── feed_id (unique)
├── name                              ├── url
├── file_type (enum)                  ├── chunks
├── file_size                         ├── inserted_at / updated_at
├── chunks                            └── deleted_at   (soft delete)
├── inserted_at
└── deleted_at (soft delete)

user_mappings
├── id (PK, serial)
├── user_id      → users.user_id       (FK, CASCADE)
├── content_id   → contents.content_id (FK, CASCADE, nullable)
├── feed_id      → feeds.feed_id       (FK, CASCADE, nullable)
├── created_at
└── CHECK: exactly one of content_id/feed_id is non-null (strict XOR)
```

**Design rationale:**
- `contents` and `feeds` are deliberately separate tables (rather than one polymorphic table) since a website feed has different lifecycle semantics (recurring re‑crawl, `updated_at`) than a static uploaded document.
- `user_mappings` is a single join table covering both relationship types via nullable FKs + a `CHECK` constraint, rather than two separate join tables — this keeps "what does this user have access to" a single query, at the cost of the XOR constraint needing to be enforced by the database rather than the type system.
- Soft deletes (`deleted_at IS NULL` filters everywhere) preserve history/auditability and let on‑disk cleanup (which is comparatively slow — `shutil.rmtree`) be decoupled from the logical delete.
- Every ID that matters externally (`content_id`, `feed_id`, `user_id`) is a UUID string rather than the internal serial PK — this means IDs are safe to hand to clients, are stable across any future table restructuring, and double as the directory name for the on‑disk FAISS/BM25 index.

---

## 5. Authentication & Session Design

- **Password storage** — Argon2 (`argon2-cffi`), which is memory‑hard and resistant to GPU cracking, in contrast to older PBKDF2/bcrypt‑only schemes.
- **Access tokens** — short‑lived (15 min default) JWTs signed with HS256 using `ACCESS_TOKEN_SECRET`. Payload carries `user_id`, `type: "access"`, `iat`, `exp`. The `type` claim exists specifically so an access token can never be replayed where a refresh token is expected, or vice versa.
- **Refresh tokens** — deliberately **not** JWTs. They're 48 bytes of `secrets.token_urlsafe` randomness — opaque, unforgeable without database access, and revocable server‑side (unlike a JWT, which remains valid until expiry no matter what). Only the **SHA‑256 hash** of the refresh token is ever persisted; verification uses `hmac.compare_digest` for constant‑time comparison to avoid timing side‑channels. This mirrors how most production auth systems (e.g. OAuth2 refresh token rotation) are built.
- **Transport** — refresh tokens travel in an `httponly`, `secure`, `samesite=strict` cookie (never exposed to client‑side JS, mitigating XSS token theft) with a `max_age` matching `REFRESH_TOKEN_TTL_DAYS`. Access tokens are returned in the JSON response body for the client to attach as an `Authorization: Bearer` header (or optionally, the middleware also accepts an `access_token` cookie).
- **Refresh flow** — `refresh_access_token` verifies the presented raw refresh token against the stored hash *and* checks expiry, then **rotates** both tokens (issues a new access token and a new refresh token, invalidating the old refresh token) — this is refresh‑token rotation, which limits the blast radius of a leaked refresh token to a single use.
- **Logout** — clears the stored refresh token/expiry server‑side and deletes the cookie, so a stolen but already‑logged‑out refresh token cannot be replayed.

---

## 6. Concurrency & Performance Choices

- **Async everywhere in the request path** — FastAPI handlers and DB helpers are `async def` end‑to‑end; CPU‑bound or blocking work (OCR, whisper transcription, ffmpeg, FAISS build/save, BM25 build) is explicitly pushed off the event loop via `asyncio.to_thread(...)`, so a single slow ingestion job doesn't stall other requests being served by the same process.
- **Parallel retrieval** — `DirectQuery.get_all_chunks` runs the BM25 and semantic lookups concurrently with `asyncio.gather`, and each of those in turn fans out one thread per requested document ID and gathers them — so querying across many documents scales with I/O/CPU parallelism rather than serial per‑ID lookups.
- **Lazy, memoized heavy‑model loading** — the OCR engine, the Whisper model, and the embedding model are all loaded once (module‑level singletons / lazy `global` initializers) and reused across requests, since loading them is the expensive part; only inference is repeated per call.
- **Connection pooling** — the async SQLAlchemy engine is configured with a sizeable pool (`pool_size=20`, `max_overflow=40`) and `pool_pre_ping=True` to survive idle‑connection drops from managed Postgres providers, plus `pool_recycle=300` to avoid stale connections.
- **PgBouncer‑friendly asyncpg config** — `statement_cache_size=0` / `prepared_statement_cache_size=0` disables asyncpg's client‑side prepared‑statement cache, which is required when the connection routes through a transaction‑mode connection pooler (as is common with hosted Postgres like Supabase) — without this, prepared statements can silently break because the underlying physical connection can change between statements.
- **Atomic index swap on re‑crawl** — `update_website()` builds the new FAISS index into a temp directory and only removes the old one after the new one is fully written and renamed into place, avoiding a window where a concurrent query could read a partially‑written index.

---

## 7. Extensibility Points

- **Adding a new file type**: add a new module under `DocsIngestion/`, following the existing `extract → chunk → embed/index → save_content_to_database` shape; add its content‑type/extension to `upload_controller.py`'s allow‑list and add a route in `upload_router.py`; add the new value to `FileType` in `models.py` and to `file_type_enum` in `schema.sql`.
- **Swapping the embedding model**: change the `model_name` default in `Embeddings/Embeddingmaker.py`; existing indexes built with a different embedding dimensionality/model will need to be rebuilt (FAISS indexes are not model‑agnostic).
- **Swapping the LLM provider**: `LLM/Llm.py` and `Query/WebSearchFallback.py` are the only two call sites that talk to an LLM directly — both are small, focused modules, so swapping Groq for another OpenAI‑compatible provider is a localized change.
- **Adding a new web‑search provider**: follow the `search_tavily`/`search_exa` pattern in `WebSearchFallback.py` (return `(context_text, source_urls)`) and add it to the provider‑fallback chain in `web_search_fallback()`.
- **Enforcing per‑user access control**: the schema and `link_user_to_content`/`link_user_to_feed`/`get_user_content_ids` helpers already exist to support "user can only query/delete their own content" — wiring them into `upload_controller.py` (call `link_user_to_content` after a successful ingest) and `query_controller.py`/`delete_controller.py` (filter/validate `ids` against `get_user_content_ids(user_id)`) is the natural next step once global auth enforcement is turned on.

---

## 8. Deployment Considerations

- **Stateful local disk** — FAISS/BM25 files live on local disk under `Data/`, not in object storage or a distributed vector DB. This means:
  - Horizontal scaling of the API to multiple instances requires a shared filesystem (e.g. NFS/EFS) or moving indexes to a networked vector store.
  - Backups need to cover `Data/` in addition to Postgres.
  - The working directory the process is launched from matters (`Path("Data").resolve()` is relative to CWD).
- **Long‑running workers as separate processes** — `Scheduler/BullMqScheduler.py` and `Backend/Utils/Rotater.py` both call `asyncio.run(main())` at import time and block forever; they must be deployed as their own processes/services (e.g. separate systemd units, Docker containers, or Kubernetes deployments), never imported into the API process.
- **GPU vs CPU** — every GPU‑capable component (embeddings via `sentence-transformers`, PaddleOCR, faster‑whisper) auto‑detects CUDA availability and falls back to CPU, so the same code runs on either, at a latency cost on CPU‑only hosts.
- **Secrets** — `ACCESS_TOKEN_SECRET`, `DATABASE_URL`, `GROQ_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY` should be injected via a secrets manager in production rather than a checked‑in `.env`.

---

## 9. Known Issues & Technical Debt

Documented honestly so they can be prioritized — none of these are exotic, all are fixable in isolation.

| # | Area | Issue |
|---|---|---|
| 1 | `Query/query_controller.py` | The endpoint only calls `get_all_chunks` (KB‑only). `get_all_chunks_with_fallback` (which would trigger the Tavily/Exa web search fallback) exists but is never invoked, even though `QueryRequest` defines `fallback_threshold`/`fallback_provider`/`max_web_results` fields for it. The web‑search fallback feature is implemented but not live. |
| 2 | `Query/DirectQuery.py` | `get_all_chunks_with_fallback` calls `web_fallback.evaluate_and_fallback(..., provider=fallback_provider, max_results=max_web_results)`, but `WebSearchFallback.evaluate_and_fallback`'s actual signature only accepts `query`, `kb_chunks`, `threshold` — calling it with `provider=`/`max_results=` will raise a `TypeError`. This needs fixing before item #1 can be wired in. |
| 3 | Score comparability | BM25 scores (higher = better, unbounded) and FAISS distance scores (lower = better, from `similarity_search_with_score`) are concatenated directly in `get_all_chunks` and later have `max()` taken across them in `is_kb_sufficient`. These are not on the same scale, so "top" chunks after merging aren't a true global ranking, and the sufficiency threshold check is not meaningful across both sources without normalization. |
| 4 | `DocsIngestion/CsvIngestion.py` | Uses `FAISS.from_documents(...)` but never imports `FAISS` — will raise `NameError` at runtime. |
| 5 | `DocsIngestion/TextIngestion.py` | Same missing‑import issue — `FAISS` is used in `_build_and_save_index_sync` but not imported. |
| 6 | `Backend/Controller/user_controller.py` | `create_user_new` calls `create_user(user_id=..., username=..., email=..., password=hashed_password)`, but `Dbhelper.user_db_helper.create_user`'s parameter is named `password_hash`, not `password` — this call will raise a `TypeError` (unexpected keyword argument). |
| 7 | `Backend/Middleware/auth.py` | `verify_token()` calls `print.warning(...)` / `print.info(...)` — `print` has no such attributes, so these branches raise `AttributeError` instead of logging. This looks like a `logger`/`print` mix‑up left over from a refactor. |
| 8 | Auth enforcement | `Backend/Middleware/auth.py` defines its **own** `FastAPI()` instance and registers `auth_middleware` on it via `@app.middleware("http")` — but that `app` object is never mounted or used by `Backend/app.py`. In practice, only the `refresh_access_token` route explicitly opts in via `dependencies=[Depends(auth_middleware)]`; upload/query/delete routes currently have **no** auth check at all. |
| 9 | Ownership enforcement | `link_user_to_content`/`link_user_to_feed` exist in `user_db_helper.py` but are never called from `upload_controller.py`, so `user_mappings` is never actually populated by the current upload flow, and `/query`/`/delete` don't check whether the requesting user owns the IDs they're operating on. |
| 10 | Website re‑crawl | `update_website()` rebuilds the FAISS index atomically but does **not** rebuild `bm25.pkl` — after a scheduled re‑crawl, keyword search results for that feed will silently drift out of sync with the new content until the feed happens to be freshly created again. |
| 11 | Idempotency store | `upload_controller.py`'s `idempotent_keys` dict is in‑process memory with no TTL/eviction and no cross‑process sharing — restarting the API process loses all idempotency history, and running multiple API replicas means a duplicate request can still slip through on a different replica. |
| 12 | File size validation | The 10 MB size check is applied in `upload_docx`/`upload_image`/`upload_csv`/`upload_audio`/`upload_video`, but `upload_pdf` does not perform the same check (`MAX_FILE_SIZE` is defined but unused). |
| 13 | Dead code | `Query/tempCodeRunnerFile.py` is an earlier, now‑superseded draft of `SemanticQuery` (missing the `_fromContent` method, different constructor signature) left in the repository — safe to delete. |
| 14 | Repo hygiene | The root `README.md` shipped in the repository was corrupted/garbled text (not valid UTF‑8 content), and there was no `DESIGN.md`, `requirements.txt`, `pyproject.toml`, or `Dockerfile` — this document set and the accompanying `README.md` are intended to close that gap. |
| 15 | Redundant object | `Backend/Middleware/auth.py` instantiates its own `FastAPI()` purely to attach a middleware decorator to it; this instance serves no other purpose and is a bit confusing next to the real app in `Backend/app.py` (related to #8). |

None of these affect the overall architecture or the soundness of the design — they're implementation bugs and half‑finished wiring that are straightforward to fix once flagged, which is the purpose of this section.

---

## 10. Summary

ZymeRag's design centers on three ideas: **(1)** keep each ingested document or crawled site as a self‑contained, UUID‑addressed unit on disk (its own FAISS + BM25 index), so retrieval can be scoped per‑query to any subset of knowledge without a shared, ever‑growing index to manage; **(2)** combine keyword and semantic retrieval rather than relying on either alone, with an optional live‑web escape hatch when local knowledge isn't enough; and **(3)** keep the operational footprint small — Postgres for metadata, Redis for lightweight coordination (job scheduling, key rotation), and local disk for the actual knowledge — rather than requiring a dedicated vector database cluster. The current codebase implements this design end‑to‑end for six content types plus websites, with a few integration gaps (documented in §9) between features that are individually complete but not yet fully connected.