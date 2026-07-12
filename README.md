# 🎭 Roleplay Studio

> A native macOS desktop app for LLM roleplay chats.
> Bots with personality, RAG knowledge base, streaming, story branching — all in one bundle.

[🇷🇺 Русская версия](README.ru.md)

---

## 🖼 Screenshots

_coming soon_

---

## ✨ Features

### 🤖 Bots & Characters

  - **Create and edit bots** — name, personality, scenario, avatar, categories
  - **V2/V3 Character Card** — import `.png` / `.webp` SillyTavern cards (with `chara` chunk parsing), export to JSON or PNG
  - **Alternate greetings** — multiple greetings per bot, ◀ ▶ switcher in the chat before the first message
  - **Categories** — Anime, Game, Fantasy, Sci-Fi, Modern, Historical, Romance, Horror, Comedy, Adventure, Custom
  - **Global drag-and-drop** — drop a `.json` / `.png` / `.webp` into the window → auto-import
  - **Three bot types** — RP (roleplay), Assistant, Agent

### 💬 Chat

  - **SSE streaming** — tokens appear one by one in real time
  - **Stop button** — interrupts generation, saves what was already typed (status `stopped`), doesn't bill extra tokens
  - **Reasoning panel** — for reasoning models (DeepSeek, QwQ, o1-style) the chain-of-thought shows in a collapsible panel under the reply, not in the message itself
  - **Branching (regenerate)** — regeneration creates an alternative version, you can switch between versions
  - **Retry** — repeat the last message
  - **Edit message** — edit a user message with context re-assembly
  - **Delete / cascade delete** — delete a single message or cascade to the end of the thread
  - **Markdown render** — code, quotes, links, emoji
  - **Actions and stats** — `[ACTION]` and `[STAT]` buttons in bot replies
  - **File attachments** — upload `.txt` / `.pdf` / `.docx` / images to a message (content goes into RAG)

### 🧠 RAG & Memory

  - **Per-bot knowledge base** — each bot has its own Chroma collection
  - **Multi-format upload** — `.txt`, `.pdf`, `.docx`, or manual entry
  - **Embeddings** — configurable model (`qwen/qwen3-embedding-8b` by default), cached
  - **Toggle in Settings** — on/off with a single switch, no restart
  - **Context compression** — after N messages, older ones fold into `short_content` (brief summaries) without losing context
  - **Thread summary** — thread recap every N messages for long roleplays
  - **Memory snapshots** — snapshots of plot state (persona, scenario, key events)
  - **Batch summarization** — parallel LLM requests for speed

### 👤 User Personas

  - **Multiple personas** — switch profiles in each thread
  - **Avatar + description** — feeds into the bot's system prompt

### 🌍 Interface

  - **3 UI languages** — English, Русский, Deutsch (i18n via `t()` helper)
  - **3 themes** — Light, Dark, System
  - **Raycast design system** — glass-morphism, double shadow rings, pill buttons, near-black background
  - **Sidebar** — Dashboard / Bots / Knowledge / Personas / Settings, collapsible
  - **Recent Chats** — latest dialogues on the Dashboard with relative time (just now / Nm / Nh / Nd)
  - **Search & filter** — full-text search across bots + category filter
  - **Setup Wizard** — 8-step onboarding for first run: Welcome → Language → Theme → Provider → Model → RAG → Persona → Finish

### 🛠 LLM & Providers

  - **OpenRouter** (default) — single API for 100+ models
  - **OpenAI-compatible** — LM Studio, Ollama, vLLM (just the base URL)
  - **Fast Model** — a separate cheap model for summarization and compression
  - **Connection test** — verify the key and available models before saving
  - **Reasoning-aware** — automatically splits `delta.content` and `delta.reasoning_content`

### 📦 Import / Export

  - **Bot export** — JSON or PNG (V2/V3 spec), imports back into SillyTavern / Risu / Agnai
  - **Chat export** — full thread history in JSON
  - **Chat import** — load a JSON chat into a new thread with persona picker
  - **Avatar upload** — `.png` / `.jpg` / `.gif` / `.webp` for bots and personas
  - **Per-bot starter bot** — built-in template to get going fast

### 🔧 Technical

  - **Clean architecture** — `domain` ← `application` ← `infrastructure`, ports via `Protocol`
  - **Alembic migrations** — schema management instead of `create_all`
  - **DI via FastAPI Depends** — `app/bootstrap.py` wires the dependency graph
  - **TDD** — 787 tests (476 backend + 311 frontend), red→green→refactor
  - **Ruff** — the only Python linter/formatter
  - **ESLint + Prettier** — Svelte + TypeScript
  - **Tauri 2** — native macOS window, auto-spawn/stop of the backend subprocess
  - **Sidecar binary** — PyInstaller backend binary (~53 MB) bundled in the `.app`

---

## 🚀 Quick Start

### Requirements

  - Python 3.13+
  - [uv](https://docs.astral.sh/uv/) — package manager
  - Node.js 24+
  - Rust (for Tauri) — `rustc` 1.88+
  - macOS 14+ (for `.app` build) or any OS for dev mode
  - An OpenRouter API key (or a local LM Studio)

### Install

```sh
# Python dependencies
uv sync

# Frontend + Tauri
cd frontend && npm install && cd ..

# Create .env and put your key in
cat > .env <<EOF
LLM_API_KEY=sk-or-...xxxx
LLM_BASE_URL=https://openrouter.ai/api/v1
CHAT_MODEL=openai/gpt-oss-20b
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
EOF
```

### Run in dev mode (Tauri)

```sh
cd frontend
npx tauri dev
```

Tauri opens a native window. Rust auto-spawns the FastAPI backend as a subprocess and kills it on close.

### Split run (for debugging backend / frontend independently)

**Terminal 1 — backend:**
```sh
uv run hypercorn api.main:app --bind 127.0.0.1:55245
```

**Terminal 2 — frontend:**
```sh
cd frontend && npx vite --port 1420
```

| Address | What |
|---------|------|
| http://127.0.0.1:1420 | Svelte SPA |
| http://127.0.0.1:55245/api/docs | Swagger UI |
| http://127.0.0.1:55245/api/health | Health check |

### First run without a key

Open `http://127.0.0.1:1420` — the backend returns `needs_setup: true` and the frontend shows the **Setup Wizard**:
Welcome → Language → Theme → Provider → API key → Model → RAG (optional) → Persona → Done.

After saving you land on the Dashboard with the built-in starter bot.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────┐
│      Tauri (macOS .app bundle)               │
│  ┌────────────────────────────────────────┐  │
│  │  WebView (Svelte 5 + Vite + Tailwind)  │  │
│  │       ↓ fetch / EventSource ↑          │  │
│  └──────────────┬─────────────────────────┘  │
│  ┌──────────────▼─────────────────────────┐  │
│  │  FastAPI sidecar (PyInstaller binary)  │  │
│  │  ── spawned by Tauri                   │  │
│  │  ── killed when the window closes      │  │
│  └──────────────┬─────────────────────────┘  │
└─────────────────┼────────────────────────────┘
                  ▼
         ┌─────────────────┐
         │  Application    │  ← services, DTOs, ports
         │  Services       │
         └──┬──────┬─────┬─┘
            ▼      ▼     ▼
        SQLite  Chroma  OpenRouter
        (SQLModel)  │    (httpx async)
                   ▼
                embeddings
```

### Clean Architecture layers

```
api/  →  app/application/  →  app/domain/
              ↓
       app/infrastructure/

domain         — Bot, ChatThread, Conversation, UserPersona, MemorySnapshot (SQLModel entities)
application    — DTOs, Protocol ports, services (BotService, ChatService, KnowledgeService, ...)
infrastructure — SQLAlchemy repositories, ChromaKnowledgeBase, OpenRouterLLM, LangGraphOrchestrator
api            — FastAPI routes + DI via `app.deps`
```

**Dependency rule:** outer layers know about inner layers, never the reverse. Swapping OpenRouter for another LLM = swap one adapter in `infrastructure/`, no changes in `application/`.

### Project structure

```
├── api/                          # FastAPI layer (routes + DI)
│   ├── main.py                   # Entrypoint, CORS, StaticFiles
│   ├── deps.py                   # DI: build_container() → Container
│   └── routes/
│       ├── bots.py               # Bot CRUD + avatar upload + character card I/E
│       ├── threads.py            # Thread CRUD + messages + summarize
│       ├── chat.py               # SSE streaming + regenerate + abort
│       ├── knowledge.py          # RAG: knowledge entries + file upload + test-search
│       ├── personas.py           # User personas
│       ├── files.py              # Thread file attachments
│       ├── config.py             # App config + reindex
│       └── setup.py              # Wizard status + providers + configure
│
├── app/                          # Clean architecture
│   ├── domain/                   # Pure entities (reserved for future use)
│   ├── application/              # Business logic
│   │   ├── dto.py                #   Pydantic DTOs (BotDTO, MessageDTO, ChatChunk, ...)
│   │   ├── ports.py              #   Protocols: BotRepository, LLMPort, KnowledgeBaseRepository, ...
│   │   ├── services/             #   BotService, ChatService, KnowledgeService, MessageSummarizer, ...
│   │   └── container.py          #   ApplicationContainer (DI graph)
│   ├── infrastructure/
│   │   ├── db/                   #   SQLModel entities + Alembic migrations
│   │   ├── repositories/         #   SQLAlchemy implementations of ports
│   │   ├── llm.py                #   OpenRouterLLM (httpx async)
│   │   ├── vectorstore.py        #   ChromaKnowledgeBase
│   │   ├── orchestration/        #   LangGraph orchestrator
│   │   └── config.py             #   Settings (pydantic + .env)
│   └── bootstrap.py              #   build_container() — composition root
│
├── frontend/                     # Svelte 5 + Vite + Tauri
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts            # Typed API client
│   │   │   ├── i18n.ts           # 3 languages (en/ru/de)
│   │   │   ├── theme.ts          # Light/Dark/System
│   │   │   ├── stores/           # Svelte stores (sidebar)
│   │   │   ├── pages/            # Dashboard, Chat, BotsPage, KnowledgePage, ...
│   │   │   ├── *.svelte          # Components (BotCard, MessageBubble, ChatInput, ...)
│   │   │   └── ui/               # Base UI (Button, Input, Toggle, Modal, ...)
│   │   ├── App.svelte
│   │   └── main.ts
│   ├── src-tauri/                # Rust + Tauri 2
│   │   ├── src/lib.rs            #   spawn + monitor FastAPI sidecar
│   │   └── tauri.conf.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── package.json
│
├── tests/                        # 787 tests (TDD: red→green→refactor)
│   ├── test_api.py               #   API integration via TestClient
│   ├── test_application_services.py
│   ├── test_chat_generation.py
│   ├── test_chat_abort.py
│   ├── test_thread_service.py
│   ├── test_summarization.py
│   ├── test_engine.py
│   ├── test_llm_prompt.py
│   ├── test_reasoning_separation.py
│   └── ...
│
├── alembic/                      # Schema migrations
│   ├── versions/
│   └── env.py
│
├── docs/
│   ├── AGENTS.md                 # Development rules (TDD, ruff, clean arch)
│   ├── superpowers/
│   │   ├── specs/                # Design specs for features
│   │   ├── plans/                # Implementation plans
│   │   └── adr/                  # Architecture Decision Records
│   ├── PLAN.md
│   ├── CHARACTER_CARD_PLAN.md
│   ├── METADATA_PLAN.md
│   └── REGEN_PLAN.md
│
├── scripts/
│   └── build-backend.sh          # PyInstaller sidecar
│
├── pyproject.toml                # Python deps + ruff + pytest
├── alembic.ini
└── .env                          # LLM_API_KEY etc.
```

---

## 🗄 Data model

6 tables in SQLite (via SQLModel + Alembic):

| Table | Purpose | Key fields |
|-------|---------|------------|
| `bots` | Characters | `name, personality, first_message, scenario, categories (JSON), bot_type, alternate_greetings (JSON), avatar_path` |
| `chat_threads` | Dialogues | `bot_id, name, summary, pending_greeting, persona_id` |
| `conversations` | Messages | `thread_id, role, content, short_content, branch_group, branch_index, is_active, generation_status` |
| `thread_files` | Attached files | `thread_id, message_id, filename, file_type, storage_path, extracted_text` |
| `user_personas` | User profiles | `name, avatar_path, description` |
| `memory_snapshots` | Plot memory | `thread_id (unique), snapshot_json` |

**`generation_status`**: `complete` / `streaming` / `stopped` / `error` — used to track interrupted generations.

---

## 🤖 Bot field reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | string (req) | Character name |
| `personality` | text (req) | Character traits, backstory |
| `description` | text | Short description (used in the bot card and previews) |
| `first_message` | text (req) | Base greeting |
| `alternate_greetings` | list[str] | Extra greetings (V2/V3 spec) |
| `scenario` | text | World / setting description |
| `categories` | list[str] | Anime / Game / Fantasy / ... |
| `bot_type` | enum | `rp` / `assistant` / `agent` |
| `avatar_path` | file | Avatar (png/jpg/gif/webp) |

---

## 📊 Testing

```sh
# All 787 tests (476 backend + 311 frontend)
uv run pytest                                # backend
cd frontend && npx vitest run                # frontend

# Verbose for a specific file
uv run pytest tests/test_chat_abort.py -v

# Just one test
uv run pytest -k "test_start_stream_registers_task_for_abort"

# Linters
uv run ruff check .                          # Python lint
uv run ruff format --check .                 # Python format
cd frontend && npm run lint                  # ESLint
cd frontend && npm run format                # Prettier
cd frontend && npm run check                 # svelte-check (types)
```

**Fixtures:** tests are self-contained — external APIs are mocked, DB is in-memory. You can run them without an OpenRouter key.

---

## ⚙️ Environment variables

All in `.env` (do not commit!) or via the environment. Defaults are for dev.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | Yes | — | API key for OpenRouter / OpenAI-compatible |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | Base URL |
| `CHAT_MODEL` | No | `openai/gpt-oss-20b` | Model for chat |
| `FAST_MODEL` | No | `openai/gpt-4o-mini` | Cheap model for summarization |
| `EMBEDDING_MODEL` | No | `qwen/qwen3-embedding-8b` | Embedding model; `""` disables RAG |
| `DEFAULT_TEMPERATURE` | No | `0.7` | LLM temperature |
| `DEFAULT_MAX_TOKENS` | No | `4096` | Token limit per response |
| `KNOWLEDGE_RELEVANCE_THRESHOLD` | No | `0.3` | Cosine threshold for RAG |
| `HISTORY_LIMIT` | No | `200` | How many recent messages to keep in context |
| `SUMMARIZE_ENABLED` | No | `true` | Generate `short_content` for messages |
| `SUMMARIZE_MIN_LENGTH` | No | `100` | Minimum message length to summarize |
| `THREAD_SUMMARY_ENABLED` | No | `true` | Update thread `summary` |
| `THREAD_SUMMARY_INTERVAL` | No | `10` | Every N messages |
| `CONTEXT_COMPRESSION_ENABLED` | No | `true` | Compress old messages |
| `CONTEXT_COMPRESSION_THRESHOLD` | No | `50` | Start compression after N messages |
| `CONTEXT_COMPRESSION_KEEP_RECENT` | No | `20` | How many recent messages to keep full |
| `SUMMARIZE_BATCH_ENABLED` | No | `true` | Parallel summarization |
| `SUMMARIZE_BATCH_SIZE` | No | `3` | How many parallel requests |
| `LANGUAGE` | No | `en` | Default UI language (en/ru/de) |
| `THEME` | No | `system` | Theme (light/dark/system) |
| `DB_PATH` | No | `~/Library/.../conversations.db` | SQLite path |
| `CHROMA_PERSIST_DIR` | No | `~/Library/.../chroma_db` | Chroma directory |

---

## 📦 Release (macOS .app)

```sh
# 1. Standalone backend binary (PyInstaller, ~53 MB)
bash scripts/build-backend.sh

# 2. macOS .app bundle → .dmg
cd frontend
npx tauri build
```

**What happens on first launch of the `.app`:**

  1. Tauri spawns the sidecar (PyInstaller binary)
  2. The backend reads `~/Library/Application Support/com.nyashkin.roleplay-studio/.env`
  3. If `.env` is missing — the API returns `needs_setup: true`
  4. The frontend shows the Setup Wizard
  5. All data (SQLite, Chroma, uploads) lives in `~/Library/Application Support/`

**Build requirements:**

  - macOS 14.0+ (Sonoma)
  - Python 3.13+ + `uv`
  - Node.js 24+
  - Rust 1.88+

**Code signing (optional):**
```json
// frontend/src-tauri/tauri.conf.json
{
  "macOS": {
    "signingIdentity": "Developer ID Application: Your Name (TEAMID)"
  }
}
```

```sh
# Check the signature
codesign -dv "Roleplay Studio.app"

# Notarize
xcrun notarytool submit "Roleplay Studio.dmg" \
  --apple-id you@example.com --password <app-specific-pwd> --team-id TEAMID
```

---

## 🗺 Roadmap

Done:
  - [x] FastAPI + SSE + file upload
  - [x] Svelte 5 + Tailwind + Tauri
  - [x] Bot CRUD + character card I/E (V2/V3 PNG)
  - [x] RAG with per-bot Chroma
  - [x] Context compression + thread summary
  - [x] User personas + thread persona binding
  - [x] Setup Wizard with 8 steps
  - [x] Setup wizard: reordering + RAG step
  - [x] Streaming abort with server-side cancellation
  - [x] Reasoning separation (collapsible panel)
  - [x] Chat import/export JSON
  - [x] Global drag-and-drop import
  - [x] Alternate greetings + greeting switcher
  - [x] 787 tests, TDD, ruff clean

In progress:
  - [ ] LangSmith tracing in production
  - [ ] Vision models (sending images to the LLM)
  - [ ] Voice input / TTS for replies

Considering:
  - 💭 Multi-user (auth)
  - 💭 Cloud sync (S3 / Supabase)
  - 💭 Sharing bots (public gallery)
