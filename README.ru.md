# 🎭 Roleplay Studio

> Нативное macOS-приложение для ролевых чатов с LLM.
> Боты с характером, RAG-база знаний, стриминг, ветвление сюжета — всё в одной обёртке.

---

## ✨ Что умеет

### 🤖 Боты и персонажи

  - **Создание и редактирование ботов** — имя, характер, сценарий, аватарка, категории
  - **V2/V3 Character Card** — импорт `.png` / `.webp` карточек SillyTavern (с парсингом `chara` chunk), экспорт в JSON или PNG
  - **Alternate greetings** — несколько приветствий у бота, ◀ ▶ переключатель в чате до первого сообщения
  - **Категории** — Anime, Game, Fantasy, Sci-Fi, Modern, Historical, Romance, Horror, Comedy, Adventure, Custom
  - **Глобальный drag-and-drop** — перетащил `.json` / `.png` / `.webp` в окно → импорт автоматически
  - **Три типа ботов** — RP (roleplay), Assistant, Agent

### 💬 Чат

  - **SSE-стриминг** — токены появляются по одному, в реальном времени
  - **Stop-кнопка** — прерывает генерацию, сохраняет то, что уже напечатано (статус `stopped`), не списывает лишние токены
  - **Reasoning panel** — для reasoning-моделей (DeepSeek, QwQ, o1-style) размышления показываются в раскрывающейся панели под ответом, не в самом сообщении
  - **Ветвление (regenerate)** — перегенерация создаёт альтернативную версию, можно переключаться между версиями
  - **Retry** — повтор последнего сообщения
  - **Edit message** — редактирование сообщения пользователя с пересбором контекста
  - **Delete / cascade delete** — удаление одного сообщения или каскадом до конца треда
  - **Markdown рендер** — код, цитаты, ссылки, эмодзи
  - **Действия и статистика** — кнопки `[ACTION]` и `[STAT]` в ответах бота
  - **File attachments** — загрузка `.txt` / `.pdf` / `.docx` / изображений к сообщению (контент уходит в RAG)

### 🧠 RAG и память

  - **Per-bot knowledge base** — у каждого бота своя Chroma-коллекция
  - **Multi-format upload** — `.txt`, `.pdf`, `.docx` или ручной ввод
  - **Embeddings** — настраиваемая модель (`qwen/qwen3-embedding-8b` по умолчанию), кэшируется
  - **Toggle в Settings** — включается/выключается одной кнопкой, без перезапуска
  - **Контекстное сжатие** — после N сообщений старые сворачиваются в `short_content` (короткие суммаризации), не теряя контекст
  - **Thread summary** — пересказ треда каждые N сообщений для долгих ролеплеев
  - **Memory snapshots** — снапшоты состояния сюжета (persona, scenario, key events)
  - **Batch summarization** — параллельные запросы к LLM для ускорения

### 👤 Персонажи пользователя

  - **Несколько persona** — переключение между профилями в каждом треде
  - **Аватарка + описание** — влияет на system prompt бота

### 🌍 Интерфейс

  - **3 языка UI** — English, Русский, Deutsch (i18n через `t()` хелпер)
  - **3 темы** — Light, Dark, System
  - **Raycast design system** — glass-морфизм, двойные кольца теней, pill-кнопки, near-black фон
  - **Sidebar** — Dashboard / Bots / Knowledge / Personas / Settings, сворачивается
  - **Recent Chats** — последние диалоги на Dashboard с relative time (just now / Nm / Nh / Nd)
  - **Search & filter** — полнотекстовый поиск по ботам + фильтр по категориям
  - **Setup Wizard** — 8-шаговый онбординг для первого запуска: Welcome → Language → Theme → Provider → Model → RAG → Persona → Finish

### 🛠 LLM и провайдеры

  - **OpenRouter** (по умолчанию) — единый API для 100+ моделей
  - **OpenAI-compatible** — LM Studio, Ollama, vLLM (только base URL)
  - **Fast Model** — отдельная дешёвая модель для суммаризации и сжатия
  - **Connection test** — проверка ключа и доступных моделей перед сохранением
  - **Reasoning-aware** — автоматически разделяет `delta.content` и `delta.reasoning_content`

### 📦 Импорт / экспорт

  - **Bot export** — JSON или PNG (V2/V3 spec), импортируется обратно в SillyTavern / Risu / Agnai
  - **Chat export** — вся история треда в JSON
  - **Chat import** — загрузка JSON чата в новый тред с выбором persona
  - **Avatar upload** — `.png` / `.jpg` / `.gif` / `.webp` для ботов и persona
  - **Per-bot starter bot** — встроенный шаблон для быстрого старта

### 🔧 Технические

  - **Clean architecture** — `domain` ← `application` ← `infrastructure`, порты через `Protocol`
  - **Alembic migrations** — schema management вместо `create_all`
  - **DI через FastAPI Depends** — `app/bootstrap.py` собирает граф зависимостей
  - **TDD** — 263 теста (unit + API integration), красный→зелёный→рефакторинг
  - **Ruff** — единственный линтер/форматтер Python
  - **ESLint + Prettier** — Svelte + TypeScript
  - **Tauri 2** — нативное окно macOS, авто-запуск/остановка бэкенда в подпроцессе
  - **Sidecar binary** — PyInstaller-бинарник бэкенда (~53 MB) в `.app`

---

## 🚀 Быстрый старт

### Требования

  - Python 3.13+
  - [uv](https://docs.astral.sh/uv/) — пакетный менеджер
  - Node.js 24+
  - Rust (для Tauri) — `rustc` 1.88+
  - macOS 14+ (для `.app` сборки) или любой OS для dev-режима
  - OpenRouter API ключ (или локальный LM Studio)

### Установка

```sh
# Python зависимости
uv sync

# Фронтенд + Tauri
cd frontend && npm install && cd ..

# Создать .env и прописать ключ
cat > .env <<EOF
OPENROUTER_API_KEY=sk-or-...xxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
CHAT_MODEL=openai/gpt-oss-20b
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
EOF
```

### Запуск в dev-режиме (Tauri)

```sh
cd frontend
npx tauri dev
```

Tauri откроет нативное окно, Rust автоматически запустит FastAPI бэкенд в подпроцессе. Убьёт его при закрытии.

### Запуск раздельный (для отладки бэка/фронта независимо)

**Терминал 1 — бэкенд:**
```sh
uv run hypercorn api.main:app --bind 127.0.0.1:55245
```

**Терминал 2 — фронтенд:**
```sh
cd frontend && npx vite --port 1420
```

| Адрес | Что |
|-------|-----|
| http://127.0.0.1:1420 | Svelte SPA |
| http://127.0.0.1:55245/api/docs | Swagger UI |
| http://127.0.0.1:55245/api/health | Health check |

### Первый запуск без ключа

Откройте `http://127.0.0.1:1420` — бэкенд вернёт `needs_setup: true`, фронт покажет **Setup Wizard**:
Welcome → Language → Theme → Provider → API key → Model → RAG (опционально) → Persona → Done.

После сохранения попадёте на Dashboard со встроенным стартер-ботом.

---

## 🏗 Архитектура

```
┌──────────────────────────────────────────────┐
│      Tauri (macOS .app bundle)               │
│  ┌────────────────────────────────────────┐  │
│  │  WebView (Svelte 5 + Vite + Tailwind)  │  │
│  │       ↓ fetch / EventSource ↑          │  │
│  └──────────────┬─────────────────────────┘  │
│  ┌──────────────▼─────────────────────────┐  │
│  │  FastAPI sidecar (PyInstaller binary)  │  │
│  │  ── запускается Tauri-ом               │  │
│  │  ── убивается при закрытии окна        │  │
│  └──────────────┬─────────────────────────┘  │
└─────────────────┼────────────────────────────┘
                  ▼
         ┌─────────────────┐
         │  Application    │  ← сервисы, DTO, порты
         │  Services       │
         └──┬──────┬─────┬─┘
            ▼      ▼     ▼
        SQLite  Chroma  OpenRouter
        (SQLModel)  │    (httpx async)
                   ▼
                embeddings
```

### Clean Architecture слои

```
api/  →  app/application/  →  app/domain/
              ↓
       app/infrastructure/

domain         — Bot, ChatThread, Conversation, UserPersona, MemorySnapshot (SQLModel entities)
application    — DTO, Protocol-порты, сервисы (BotService, ChatService, KnowledgeService, ...)
infrastructure — SQLAlchemy-репозитории, ChromaKnowledgeBase, OpenRouterLLM, LangGraphOrchestrator
api            — FastAPI роуты + DI через `app.deps`
```

**Правило зависимостей:** внешние слои знают о внутренних, не наоборот. Замена OpenRouter на другой LLM = замена одного адаптера в `infrastructure/`, без изменений в `application/`.

### Структура проекта

```
├── api/                          # FastAPI слой (роуты + DI)
│   ├── main.py                   # Entrypoint, CORS, StaticFiles
│   ├── deps.py                   # DI: build_container() → Container
│   └── routes/
│       ├── bots.py               # CRUD ботов + avatar upload + character card I/E
│       ├── threads.py            # CRUD тредов + messages + summarize
│       ├── chat.py               # SSE-стриминг + regenerate + abort
│       ├── knowledge.py          # RAG: knowledge entries + file upload + test-search
│       ├── personas.py           # User personas
│       ├── files.py              # Thread file attachments
│       ├── config.py             # App config + reindex
│       └── setup.py              # Wizard status + providers + configure
│
├── app/                          # Чистая архитектура
│   ├── domain/                   # (на будущее) pure entities
│   ├── application/              # Бизнес-логика
│   │   ├── dto.py                #   Pydantic DTO (BotDTO, MessageDTO, ChatChunk, ...)
│   │   ├── ports.py              #   Protocol: BotRepository, LLMPort, KnowledgeBaseRepository, ...
│   │   ├── services/             #   BotService, ChatService, KnowledgeService, MessageSummarizer, ...
│   │   └── container.py          #   ApplicationContainer (DI-граф)
│   ├── infrastructure/
│   │   ├── db/                   #   SQLModel entities + Alembic миграции
│   │   ├── repositories/         #   SQLAlchemy-реализации портов
│   │   ├── llm.py                #   OpenRouterLLM (httpx async)
│   │   ├── vectorstore.py        #   ChromaKnowledgeBase
│   │   ├── orchestration/        #   LangGraph оркестратор
│   │   └── config.py             #   Settings (pydantic + .env)
│   └── bootstrap.py              #   build_container() — корень композиции
│
├── frontend/                     # Svelte 5 + Vite + Tauri
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts            # Типизированный API-клиент
│   │   │   ├── i18n.ts           # 3 языка (en/ru/de)
│   │   │   ├── theme.ts          # Light/Dark/System
│   │   │   ├── stores/           # Svelte stores (sidebar)
│   │   │   ├── pages/            # Dashboard, Chat, BotsPage, KnowledgePage, ...
│   │   │   ├── *.svelte          # Компоненты (BotCard, MessageBubble, ChatInput, ...)
│   │   │   └── ui/               # Базовые UI (Button, Input, Toggle, Modal, ...)
│   │   ├── App.svelte
│   │   └── main.ts
│   ├── src-tauri/                # Rust + Tauri 2
│   │   ├── src/lib.rs            #   spawn + monitor FastAPI sidecar
│   │   └── tauri.conf.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── package.json
│
├── tests/                        # 263 теста (TDD: red→green→refactor)
│   ├── test_api.py               #   API integration через TestClient
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
├── alembic/                      # Миграции схемы
│   ├── versions/
│   └── env.py
│
├── docs/
│   ├── AGENTS.md                 # Правила разработки (TDD, ruff, clean arch)
│   ├── superpowers/
│   │   ├── specs/                # Дизайн-спеки фич (5 шт)
│   │   ├── plans/                # Планы имплементации
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
└── .env                          # OPENROUTER_API_KEY etc.
```

---

## 🗄 Модель данных

6 таблиц в SQLite (через SQLModel + Alembic):

| Таблица | Назначение | Ключевые поля |
|---------|-----------|---------------|
| `bots` | Персонажи | `name, personality, first_message, scenario, categories (JSON), bot_type, alternate_greetings (JSON), avatar_path` |
| `chat_threads` | Диалоги | `bot_id, name, summary, pending_greeting, persona_id` |
| `conversations` | Сообщения | `thread_id, role, content, short_content, branch_group, branch_index, is_active, generation_status` |
| `thread_files` | Прикреплённые файлы | `thread_id, message_id, filename, file_type, storage_path, extracted_text` |
| `user_personas` | Профили юзера | `name, avatar_path, description` |
| `memory_snapshots` | Память сюжета | `thread_id (unique), snapshot_json` |

**`generation_status`**: `complete` / `streaming` / `stopped` / `error` — для отслеживания прерванных генераций.

---

## 🤖 Поле Bot — справочник

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | string (req) | Имя персонажа |
| `personality` | text (req) | Характер, черты, бэкстори |
| `description` | text | Краткое описание (используется в карточке бота и в превью) |
| `first_message` | text (req) | Базовое приветствие |
| `alternate_greetings` | list[str] | Дополнительные приветствия (V2/V3 spec) |
| `scenario` | text | Описание мира/сеттинга |
| `categories` | list[str] | Anime / Game / Fantasy / ... |
| `bot_type` | enum | `rp` / `assistant` / `agent` |
| `avatar_path` | file | Аватарка (png/jpg/gif/webp) |

---

## 📊 Тестирование

```sh
# Все 263 теста
uv run pytest

# Verbose для конкретного файла
uv run pytest tests/test_chat_abort.py -v

# Только один тест
uv run pytest -k "test_start_stream_registers_task_for_abort"

# Линтер
uv run ruff check .
uv run ruff format --check .

# Фронт
cd frontend
npm run test          # vitest
npm run lint          # eslint
npm run check         # svelte-check
npm run format        # prettier --check
```

**Фикстуры:** тесты самодостаточны — внешние API замоканы, БД в памяти. Можно гонять без ключа OpenRouter.

---

## ⚙️ Переменные окружения

Все — в `.env` (не коммитить!) или через env. Дефолты — для dev.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | API ключ для OpenRouter / OpenAI-compat |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1` | Базовый URL |
| `CHAT_MODEL` | No | `openai/gpt-oss-20b` | Модель для чата |
| `FAST_MODEL` | No | `openai/gpt-4o-mini` | Дешёвая модель для суммаризации |
| `EMBEDDING_MODEL` | No | `qwen/qwen3-embedding-8b` | Модель эмбеддингов; `""` отключает RAG |
| `DEFAULT_TEMPERATURE` | No | `0.7` | Температура LLM |
| `DEFAULT_MAX_TOKENS` | No | `4096` | Лимит токенов на ответ |
| `KNOWLEDGE_RELEVANCE_THRESHOLD` | No | `0.3` | Порог cosine для RAG |
| `HISTORY_LIMIT` | No | `200` | Сколько последних сообщений держать в контексте |
| `SUMMARIZE_ENABLED` | No | `true` | Генерировать `short_content` для сообщений |
| `SUMMARIZE_MIN_LENGTH` | No | `100` | Минимальная длина сообщения для суммаризации |
| `THREAD_SUMMARY_ENABLED` | No | `true` | Обновлять `summary` треда |
| `THREAD_SUMMARY_INTERVAL` | No | `10` | Каждые N сообщений |
| `CONTEXT_COMPRESSION_ENABLED` | No | `true` | Сжимать старые сообщения |
| `CONTEXT_COMPRESSION_THRESHOLD` | No | `50` | Начинать сжатие после N сообщений |
| `CONTEXT_COMPRESSION_KEEP_RECENT` | No | `20` | Сколько последних оставлять полными |
| `SUMMARIZE_BATCH_ENABLED` | No | `true` | Параллельная суммаризация |
| `SUMMARIZE_BATCH_SIZE` | No | `3` | Сколько параллельных запросов |
| `LANGUAGE` | No | `en` | Язык UI по умолчанию (en/ru/de) |
| `THEME` | No | `system` | Тема (light/dark/system) |
| `DB_PATH` | No | `~/Library/.../conversations.db` | Путь к SQLite |
| `CHROMA_PERSIST_DIR` | No | `~/Library/.../chroma_db` | Директория Chroma |

---

## 📦 Релиз (macOS .app)

```sh
# 1. Standalone-бинарник бэкенда (PyInstaller, ~53 MB)
bash scripts/build-backend.sh

# 2. macOS .app bundle → .dmg
cd frontend
npx tauri build
```

**Что происходит при первом запуске `.app`:**

  1. Tauri запускает sidecar (PyInstaller-бинарник)
  2. Бэкенд читает `~/Library/Application Support/com.nyashkin.roleplay-studio/.env`
  3. Если `.env` нет — API возвращает `needs_setup: true`
  4. Фронт показывает Setup Wizard
  5. Все данные (SQLite, Chroma, uploads) — в `~/Library/Application Support/`

**Требования для сборки:**

  - macOS 14.0+ (Sonoma)
  - Python 3.13+ + `uv`
  - Node.js 24+
  - Rust 1.88+

**Code signing (опционально):**
```json
// frontend/src-tauri/tauri.conf.json
{
  "macOS": {
    "signingIdentity": "Developer ID Application: Your Name (TEAMID)"
  }
}
```

```sh
# Проверить подпись
codesign -dv "Roleplay Studio.app"

# Нотаризация
xcrun notarytool submit "Roleplay Studio.dmg" \
  --apple-id you@example.com --password <app-specific-pwd> --team-id TEAMID
```

---

## 🗺 Roadmap

Сделанное:
  - [x] FastAPI + SSE + file upload
  - [x] Svelte 5 + Tailwind + Tauri
  - [x] Bot CRUD + character card I/E (V2/V3 PNG)
  - [x] RAG с per-bot Chroma
  - [x] Контекстное сжатие + thread summary
  - [x] User personas + thread persona binding
  - [x] Setup Wizard с 8 шагами
  - [x] Setup wizard: reordering + RAG step
  - [x] Streaming abort с server-side cancellation
  - [x] Reasoning separation (collapsible panel)
  - [x] Chat import/export JSON
  - [x] Global drag-and-drop import
  - [x] Alternate greetings + greeting switcher
  - [x] 263 тестов, TDD, ruff clean

В работе:
  - [ ] LangSmith tracing в production
  - [ ] Vision models (отправка картинок в LLM)
  - [ ] Voice input / TTS ответов

Подумать:
  - 💭 Multi-user (auth)
  - 💭 Cloud sync (S3 / Supabase)
  - 💭 Sharing bots (public gallery)
