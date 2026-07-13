/// <reference types="svelte" />

const DEFAULT_API_BASE = 'http://127.0.0.1:55245';

// When running behind the Vite dev server (host or Docker) the
// API is reachable on the same origin via the /api proxy. We
// detect that by checking the build-time VITE_USE_PROXY flag —
// set automatically by docker-compose and ignored otherwise.
//
// This means `npm run dev` on the host still hits :55245
// directly (the previous behaviour, no surprises), but
// `docker compose up` automatically uses relative URLs that go
// through Vite → backend container. No environment-switch dance
// needed at the JS layer.
const USE_PROXY =
  // Vite injects import.meta.env.* at build time; the boolean
  // cast works whether the flag was set as `true` or `"true"`.
  // string('true') === true, so the negation below is safe.
  // We invert because a missing flag is the historical default
  // (direct fetch from :55245).
  String(import.meta.env?.VITE_USE_PROXY ?? '').toLowerCase() === 'true';

const PROXY_API_BASE =
  typeof window !== 'undefined' && window.location?.origin
    ? window.location.origin
    : DEFAULT_API_BASE;

const INITIAL_API_BASE = USE_PROXY ? PROXY_API_BASE : DEFAULT_API_BASE;

/**
 * Resolved API base URL. Re-reads `localStorage.serverUrl` on every
 * `apiBase()` call. Use as `apiBase()` instead of `API_BASE` in
 * template literals for dynamic resolution.
 *
 * Tauri Android wrapper: set `localStorage.serverUrl` before
 * importing this module to redirect the app to a remote server.
 */
export function apiBase(): string {
  try {
    const stored = localStorage.getItem('serverUrl');
    if (stored && stored.trim()) {
      return stored.trim().replace(/\/+$/, '');
    }
  } catch {
    /* localStorage unavailable — fall through */
  }
  return INITIAL_API_BASE;
}

/**
 * @deprecated Use `apiBase()` for dynamic resolution. Kept as the
 * initial-value export for back-compat with imports like
 * `import { API_BASE } from './api'`.
 */
export const API_BASE = apiBase();

export type BotType = 'agent' | 'assistant' | 'rp';

/** Get full avatar URL from a stored path. */
export function avatarUrl(path: null | string): null | string {
  if (!path) return null;
  return `${apiBase()}${path}`;
}

/**
 * Get thumbnail URL for an avatar path.
 * Inserts size suffix before the extension: avatar.png → avatar_50.png
 * Falls back to original path if thumbnail not available.
 */
export function thumbUrl(path: null | string, size: 50 | 200 | 500 = 200): null | string {
  if (!path) return null;
  const dot = path.lastIndexOf('.');
  if (dot === -1) return `${apiBase()}${path}`;
  const base = path.substring(0, dot);
  const ext = path.substring(dot);
  return `${apiBase()}${base}_${size}${ext}`;
}

export const BOT_TYPES: { description: string; icon: string; label: string; value: BotType }[] = [
  {
    description: 'Character with personality, scenario, first message',
    icon: '🎭',
    label: 'RolePlay',
    value: 'rp',
  },
  {
    description: 'Helpful AI with system prompt',
    icon: '🤖',
    label: 'Assistant',
    value: 'assistant',
  },
  { description: 'AI agent with file upload & tools', icon: '🛠️', label: 'Agent', value: 'agent' },
];

export interface AppConfig {
  api_key_configured: boolean;
  chat_model: string;
  chroma_persist_dir: string;
  context_compression_enabled: boolean;
  context_compression_keep_recent: number;
  context_compression_threshold: number;
  db_path: string;
  debug_enabled: boolean;
  /** Raw DEBUG env value (e.g. "true", "1", ""). Lets the UI tell
   *  "unset" apart from "explicitly false" if we ever need to. */
  debug_env_raw: string;
  default_max_tokens: number;
  default_temperature: number;
  embedding_api_key_configured: boolean;
  embedding_base_url: string;
  embedding_model: string;
  /** Active environment label — e.g. "development", "production",
   *  or whatever the user set in the ENVIRONMENT env var. Used by
   *  the System section in Settings to flag dev-mode explicitly. */
  environment: string;
  fast_model: string;
  history_limit: number;
  knowledge_relevance_threshold: number;
  language: string;
  llm_base_url: string;
  summarize_enabled: boolean;
  summarize_max_tokens: number;
  summarize_min_length: number;
  theme: string;
  thread_summary_enabled: boolean;
  thread_summary_interval: number;
  // ── TTS (text-to-speech) ────────────────────────────────────
  // Server mirrors these so the Settings page can edit them in place.
  // ``tts_api_key_configured`` is a boolean (not the key itself) so the
  // page can show a "configured" badge without leaking the secret.
  tts_api_key_configured: boolean;
  tts_base_url: string;
  tts_cache_dir: string;
  tts_model: string;
  /** Active provider — one of "disabled", "mock", "minimax". */
  tts_provider: 'disabled' | 'minimax' | 'mock';
  /** Speech rate (0.5..2.0) — clamped by the server. */
  tts_speed: number;
  tts_voice_id: string;
  /** Backend package version, mirrored from pyproject.toml. */
  version: string;
}

export interface Bot {
  alternate_greetings: string[];
  avatar_path: null | string;
  bot_type: BotType;
  categories: string[];
  /** Categories that were saved on this bot but are no longer
   *  defined in the user-managed list. The picker hides them; the
   *  card surfaces them as a "stale" badge so the user can clean up.
   *  Empty array when every category is currently valid. */
  categories_invalid: string[];
  description: string;
  /** Floating system reminder injected right before the last user turn on
   *  every chat request. Empty string = no floating prompt (default). */
  dynamic_system_prompt?: string;
  first_message: string;
  id: number;
  /** V1/V2/V3 character card `mes_example` — few-shot dialogue examples.
   *  Optional in the interface for backward compatibility with bots created
   *  before the migration (defaults to empty string in the API). */
  mes_example?: string;
  name: string;
  personality: string;
  scenario: string;
  thread_count: number;
  /** System prompt for the background state-update task. The bot
   *  developer owns the output format via this prompt. Empty string =
   *  no background state generation. */
  world_state_prompt?: string;
}

/** The shape of the serialized bot inside a version snapshot. Mirrors
 * the editable fields of `Bot` — id and relationships are omitted. */
export interface BotSnapshot {
  alternate_greetings: string[];
  avatar_path: null | string;
  bot_type: BotType;
  categories: string[];
  description: string;
  dynamic_system_prompt: string;
  first_message: string;
  mes_example: string;
  name: string;
  personality: string;
  scenario: string;
  world_state_prompt: string;
}

/** A snapshot of a Bot at the moment of capture. */
export interface BotVersion {
  bot_id: number;
  created_at: string;
  id: number;
  note: string;
  /** Snapshot payload — present only on single-version fetches and on
   *  the create response. List responses keep it as null to keep the
   *  timeline payload small. */
  snapshot: BotSnapshot | null;
  source: 'auto' | 'manual';
  version_number: number;
}

export interface KnowledgeEntry {
  chunk_count?: number;
  content: string;
  file_name?: string;
  id: string;
  source_type?: string;
}

export interface KnowledgeStatusResponse {
  embedding_base_url: string;
  embedding_model: string;
  reindex_in_progress: boolean;
  reindex_job_id: null | string;
  stale_bot_ids: number[];
}

export interface LLMDebugInfo {
  max_tokens: null | number;
  messages: Array<{ content: string; role: string }>;
  model: string;
  temperature: null | number;
}

export interface LLMUsage {
  completion_tokens: number;
  prompt_tokens: number;
  total_tokens: number;
}

export interface Message {
  branch_group: null | string;
  branch_index: number;
  content: string;
  created_at: null | string;
  /** Captured at stream time so the chat UI can render the floating
   *  prompt panel. Set on assistant messages only when the bot has a
   *  non-empty dynamic_system_prompt. */
  dynamic_system_prompt?: null | string;
  id: null | number;
  is_active: boolean;
  /** Chain-of-thought from a reasoning-capable LLM (DeepSeek, QwQ, ...).
   *  Persisted to the DB so the panel survives page reloads / thread
   *  reopens / cross-device navigations. Missing / empty on messages
   *  from non-reasoning models. The MessageBubble hides the panel
   *  when this is undefined or empty. */
  reasoning?: string;
  role: 'assistant' | 'system' | 'user';
  short_content: string;
  /** Per-message world-state snapshot (opaque string — bot author
   *  owns the format via ``Bot.world_state_prompt``). Populated by the
   *  background state-update task after each assistant response;
   *  undefined on messages that predate the feature or where the bot
   *  has no world_state_prompt. */
  state?: null | string;
  versions?: Message[];
}

export interface Persona {
  avatar_path: null | string;
  description: string;
  id: number;
  name: string;
}

export interface RecentThread {
  bot_avatar_path: null | string;
  bot_categories: string[];
  bot_id: number;
  bot_name: string;
  bot_personality: string;
  last_message_at: null | string;
  last_message_preview: string;
  persona_avatar_path: null | string;
  persona_name: null | string;
  summary: null | string;
  thread_id: number;
}

/** Header-level stats from `GET /api/threads/{id}/stats`.
 *
 * Distinct from `listMessages` — `message_count` is the real full-thread
 * total (including older pages), independent of the 50-message pagination
 * window the chat UI fetches. The chat header binds to this, never to the
 * length of the locally-loaded messages array.
 */
// (Defined further down so the file remains alpha-sorted by interface
// name for ESLint perfectionist's sort-modules rule. The interface
// itself is the same; see chat header binding for usage.)

export interface ReindexJobState {
  bots_done: number;
  current_bot_entries_done: number;
  current_bot_entries_total: number;
  current_bot_id: null | number;
  current_bot_name: null | string;
  error: null | string;
  finished_at: null | string;
  job_id: string;
  started_at: string;
  status: ReindexJobStatus;
  total_bots: number;
}

export type ReindexJobStatus = 'cancelled' | 'completed' | 'failed' | 'pending' | 'running';

export interface ReindexStartResponse {
  job_id: null | string;
  ok: boolean;
  stale_bots: number[];
}

export interface Thread {
  bot_id: number;
  created_at: null | string;
  id: number;
  name: string;
  /** FK to the source thread (forks only). Null for root threads. */
  parent_thread_id?: null | number;
  persona_id: null | number;
  persona_name: null | string;
  summary: null | string;
}

export interface ThreadFileDTO {
  created_at: null | string;
  extracted_text: null | string;
  file_type: string;
  filename: string;
  id: number;
  message_id: null | number;
  storage_path: string;
  thread_id: number;
}

/** Header-level stats from `GET /api/threads/{id}/stats`.
 *
 * Distinct from `listMessages` — `message_count` is the real full-thread
 * total (including older pages), independent of the 50-message pagination
 * window the chat UI fetches. The chat header binds to this, never to the
 * length of the locally-loaded messages array.
 *
 * Note: declared after ``ThreadFileDTO`` so ESLint perfectionist's
 * sort-modules rule sees the alpha order (``Th...Fi...`` then ``Th...St...``).
 */
export interface ThreadStats {
  message_count: number;
  thread_id: number;
  token_estimate: number;
}

export class ApiError extends Error {
  detail: string;
  status: number;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  /** Cancel an in-flight LLM stream for the given thread. Idempotent. */
  abortGeneration: (threadId: number): Promise<{ partial_saved: boolean; was_active: boolean }> =>
    fetch(`${apiBase()}/api/threads/${threadId}/abort`, { method: 'POST' }).then((r) => {
      // 204 No Content (or any 2xx without body) → was_active=false.
      if (!r.ok && r.status !== 204) {
        throw new Error(`abort failed: ${r.status}`);
      }
      return r.json().catch(() => ({ partial_saved: false, was_active: false }));
    }),

  addCategory: (name: string) =>
    request<string[]>('/api/bots/categories', {
      body: JSON.stringify({ name }),
      method: 'POST',
    }),

  addKnowledge: (botId: number, content: string) =>
    request<{ ok: boolean }>(`/api/knowledge/${botId}`, {
      body: JSON.stringify({ content }),
      method: 'POST',
    }),
  addKnowledgeFile: async (botId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${apiBase()}/api/knowledge/${botId}/upload`, {
      body: formData,
      method: 'POST',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || 'Upload failed');
    }
    return res.json() as Promise<{ chunk_count: number; file_name: string; status: string }>;
  },

  cancelReindex: (jobId: string) =>
    request<{ ok: boolean }>(`/api/config/knowledge/reindex/${jobId}/cancel`, { method: 'POST' }),

  cascadeDeleteMessages: (threadId: number, messageId: number) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/messages/${messageId}/cascade`, {
      method: 'DELETE',
    }),
  // Categories
  categories: () => request<string[]>('/api/bots/categories'),
  clearThread: (id: number) =>
    request<{ ok: boolean }>(`/api/threads/${id}/clear`, { method: 'POST' }),
  // Config
  config: () => request<AppConfig>('/api/config'),
  createBot: (data: {
    avatar_path?: null | string;
    bot_type?: BotType;
    categories?: string[];
    description?: string;
    first_message: string;
    name: string;
    personality: string;
    scenario?: string;
  }) => request<{ id: number }>('/api/bots', { body: JSON.stringify(data), method: 'POST' }),
  createBotVersion: (botId: number, note: string) =>
    request<BotVersion>(`/api/bots/${botId}/versions`, {
      body: JSON.stringify({ note }),
      method: 'POST',
    }),
  createPersona: (data: { avatar_path?: null | string; description?: string; name: string }) =>
    request<{ id: number }>('/api/personas', { body: JSON.stringify(data), method: 'POST' }),
  createThread: (botId: number, personaId?: null | number) =>
    request<{ id: number }>(`/api/bots/${botId}/threads`, {
      body: JSON.stringify({ persona_id: personaId ?? null }),
      method: 'POST',
    }),

  deleteBot: (id: number) => request<{ ok: boolean }>(`/api/bots/${id}`, { method: 'DELETE' }),
  deleteBotVersion: (botId: number, versionId: number) =>
    request<{ ok: boolean }>(`/api/bots/${botId}/versions/${versionId}`, {
      method: 'DELETE',
    }),
  deleteCategory: (name: string) =>
    request<string[]>(`/api/bots/categories/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  deleteFile: (threadId: number, fileId: number) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/files/${fileId}`, { method: 'DELETE' }),
  deleteKnowledge: (botId: number, entryId: string) =>
    request<{ ok: boolean }>(`/api/knowledge/${botId}/${entryId}`, { method: 'DELETE' }),

  deleteKnowledgeFile: (botId: number, fileName: string) =>
    request<{ deleted: number; ok: boolean }>(
      `/api/knowledge/${botId}/file/${encodeURIComponent(fileName)}`,
      { method: 'DELETE' },
    ),

  deleteLastMessage: (threadId: number) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/messages/last`, { method: 'DELETE' }),

  deleteMessage: (threadId: number, messageId: number) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/messages/${messageId}`, {
      method: 'DELETE',
    }),
  deletePersona: (id: number) =>
    request<{ ok: boolean }>(`/api/personas/${id}`, { method: 'DELETE' }),
  deleteThread: (id: number) =>
    request<{ ok: boolean }>(`/api/threads/${id}`, { method: 'DELETE' }),
  // ── Bot Export / Import ────────────────────────────────────────────
  exportBot: async (id: number, filename: string, format: 'json' | 'png' = 'json') => {
    const res = await fetch(`${apiBase()}/api/bots/${id}/export?format=${format}`, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename.endsWith(`.${format}`) ? filename : `${filename}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  // ── Chat Import / Export ────────────────────────────────────────────
  exportChat: async (threadId: number) => {
    const res = await fetch(`${apiBase()}/api/threads/${threadId}/export`, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `thread-${threadId}-export.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  findThreadByBotAndPersona: (botId: number, personaId: number) =>
    request<{ thread: null | Thread }>(`/api/bots/${botId}/threads/find?persona_id=${personaId}`),

  /** Snapshot the conversation up to ``messageId`` into a new thread.
   *
   * User-facing flow: the user clicks the fork icon on a message in
   * the chat UI; the backend returns the new thread's ``ThreadDTO``
   * so the frontend can redirect. ``messageId`` MUST belong to the
   * source thread's active chain — otherwise the backend returns
   * 404, which the route layer surfaces verbatim so the caller can
   * decide whether to show an error toast.
   *
   * Returns the full ``Thread`` so the caller can wire the new id
   * into the chat header without a follow-up GET.
   */
  forkThread: (threadId: number, messageId: number): Promise<Thread> =>
    request<Thread>(`/api/threads/${threadId}/fork`, {
      body: JSON.stringify({ message_id: messageId }),
      method: 'POST',
    }),
  getBot: (id: number) => request<Bot>(`/api/bots/${id}`),

  getBotVersion: (botId: number, versionId: number) =>
    request<BotVersion>(`/api/bots/${botId}/versions/${versionId}`),

  // Knowledge (RAG) — embedding model changes & reindex
  getKnowledgeStatus: () => request<KnowledgeStatusResponse>('/api/config/knowledge/status'),

  // Message versions
  getMessageVersions: (threadId: number, messageId: number) =>
    request<{ versions: Message[] }>(`/api/threads/${threadId}/messages/${messageId}/versions`),

  getPersona: (id: number) => request<Persona>(`/api/personas/${id}`),
  // Threads
  getThread: (id: number) => request<Thread>(`/api/threads/${id}`),
  // Header-level thread stats used by the chat header — full count,
  // independent of listMessages pagination. See Chat.svelte binding.
  getThreadStats: (threadId: number) => request<ThreadStats>(`/api/threads/${threadId}/stats`),
  // Health
  health: () => request<{ status: string }>('/api/health'),
  importBot: async (file: File): Promise<{ id: number }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${apiBase()}/api/bots/import`, {
      body: form,
      method: 'POST',
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },
  importChat: async (
    botId: number,
    file: File,
    personaId?: null | number,
  ): Promise<{ message_count: number; ok: boolean; thread_id: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    if (personaId != null) formData.append('persona_id', String(personaId));
    const res = await fetch(`${apiBase()}/api/bots/${botId}/import-chat`, {
      body: formData,
      method: 'POST',
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },
  // Bots
  listBots: () => request<Bot[]>('/api/bots'),

  listBotThreads: (botId: number) => request<Thread[]>(`/api/bots/${botId}/threads`),
  // Bot versioning
  listBotVersions: (botId: number) => request<BotVersion[]>(`/api/bots/${botId}/versions`),
  listFilesForMessage: (threadId: number, messageId: number) =>
    request<ThreadFileDTO[]>(`/api/threads/${threadId}/messages/${messageId}/files`),
  // Knowledge
  listKnowledge: (botId: number) => request<KnowledgeEntry[]>(`/api/knowledge/${botId}`),
  // Pagination uses a keyset cursor: pass `beforeId` to load messages
  // older than that id. When `beforeId` is null the server returns the
  // newest page (current behaviour).
  listMessages: (id: number, limit = 50, beforeId: null | number = null) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (beforeId !== null) params.set('before_id', String(beforeId));
    return request<Message[]>(`/api/threads/${id}/messages?${params}`);
  },

  // Personas
  listPersonas: () => request<Persona[]>('/api/personas'),

  // Recent threads
  listRecentThreads: (limit = 30, botId?: number) =>
    request<RecentThread[]>(`/api/threads/recent?limit=${limit}${botId ? `&bot_id=${botId}` : ''}`),

  listThreadFiles: (threadId: number) => request<ThreadFileDTO[]>(`/api/threads/${threadId}/files`),

  // Message regeneration (SSE stream)
  regenerateMessage: async (
    threadId: number,
    messageId: number,
    botId: number,
    personaId?: null | number,
  ): Promise<Response> => {
    return fetch(`${apiBase()}/api/threads/${threadId}/messages/${messageId}/regenerate`, {
      body: JSON.stringify({ bot_id: botId, persona_id: personaId ?? null }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  // Reindex
  reindexKnowledge: () =>
    request<{ detail: string; ok: boolean }>('/api/config/reindex', { method: 'POST' }),

  renameCategory: (oldName: string, newName: string) =>
    request<string[]>('/api/bots/categories/rename', {
      body: JSON.stringify({ new_name: newName, old_name: oldName }),
      method: 'POST',
    }),
  renameThread: (id: number, name: string) =>
    request<{ ok: boolean }>(`/api/threads/${id}?name=${encodeURIComponent(name)}`, {
      method: 'PUT',
    }),
  replaceCategories: (categories: string[]) =>
    request<string[]>('/api/bots/categories', {
      body: JSON.stringify({ categories }),
      method: 'PUT',
    }),
  restoreBotVersion: (botId: number, versionId: number) =>
    request<{ ok: boolean; restored_from: number }>(
      `/api/bots/${botId}/versions/${versionId}/restore`,
      { method: 'POST' },
    ),

  // Message retry (reuse existing user message, no duplicate)
  retryMessage: async (
    threadId: number,
    userMessageId: number,
    botId: number,
    personaId?: null | number,
  ): Promise<Response> => {
    return fetch(`${apiBase()}/api/threads/${threadId}/messages/${userMessageId}/retry`, {
      body: JSON.stringify({ bot_id: botId, persona_id: personaId ?? null }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },
  setFirstMessage: (threadId: number, greetingIndex: number) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/first-message`, {
      body: JSON.stringify({ greeting_index: greetingIndex }),
      method: 'PUT',
    }),

  setThreadPersona: (id: number, personaId: null | number) =>
    request<{ ok: boolean }>(`/api/threads/${id}/persona?persona_id=${personaId ?? 0}`, {
      method: 'PUT',
    }),

  // Reindex a stale embedding collection (returns job_id, supports SSE streaming + cancel)
  startReindex: () =>
    request<ReindexStartResponse>('/api/config/knowledge/reindex', { method: 'POST' }),
  // Thread summary
  summarizeThread: (threadId: number) =>
    request<{ ok: boolean; summary: null | string }>(`/api/threads/${threadId}/summarize`, {
      method: 'POST',
    }),
  // Switch active version
  switchVersion: (threadId: number, messageId: number, versionId: number) =>
    request<{ message: Message; success: boolean }>(
      `/api/threads/${threadId}/messages/${messageId}/switch/${versionId}`,
      { method: 'POST' },
    ),
  testSearchKnowledge: async (
    botId: number,
    query: string,
    topK = 5,
  ): Promise<{ results: { content: string; score: number }[] }> => {
    return request(`/api/knowledge/${botId}/test-search`, {
      body: JSON.stringify({ query, top_k: topK }),
      method: 'POST',
    });
  },
  updateBot: (
    id: number,
    data: {
      alternate_greetings?: string[];
      avatar_path?: null | string;
      bot_type?: BotType;
      categories?: string[];
      description?: string;
      dynamic_system_prompt?: string;
      first_message: string;
      mes_example?: string;
      name: string;
      personality: string;
      scenario?: string;
      world_state_prompt?: string;
    },
  ) => request<{ ok: boolean }>(`/api/bots/${id}`, { body: JSON.stringify(data), method: 'PUT' }),

  updateConfig: (data: {
    context_compression_enabled?: boolean;
    context_compression_keep_recent?: number;
    context_compression_threshold?: number;
    embedding_api_key?: null | string;
    embedding_base_url?: null | string;
    embedding_model?: string;
    fast_model?: string;
    history_limit?: number;
    knowledge_relevance_threshold?: number;
    language?: string;
    max_tokens?: number;
    summarize_enabled?: boolean;
    summarize_max_tokens?: number;
    summarize_min_length?: number;
    temperature?: number;
    theme?: string;
    thread_summary_enabled?: boolean;
    thread_summary_interval?: number;
    // TTS keys mirror the pydantic schema. ``tts_provider`` is a
    // union of the three legal values (validated server-side).
    tts_api_key?: null | string;
    tts_base_url?: null | string;
    tts_cache_dir?: null | string;
    tts_model?: null | string;
    tts_provider?: 'disabled' | 'minimax' | 'mock' | null;
    tts_speed?: null | number;
    tts_voice_id?: null | string;
  }) => request<AppConfig>('/api/config', { body: JSON.stringify(data), method: 'POST' }),

  updateKnowledge: (botId: number, entryId: string, content: string) =>
    request<{ ok: boolean }>(`/api/knowledge/${botId}/${entryId}`, {
      body: JSON.stringify({ content }),
      method: 'PUT',
    }),

  // Message editing. ``state`` is the world-state snapshot column
  // on the assistant message table — pass ``undefined`` to keep the
  // original message's state on the new branch (branching fidelity),
  // pass ``""`` to explicitly clear it, pass a string to overwrite.
  // The EditMessageModal's "Save" sends the currently-typed value
  // (including empty), so the network shape is always present.
  updateMessage: (threadId: number, messageId: number, content: string, state?: null | string) =>
    request<{ ok: boolean }>(`/api/threads/${threadId}/messages/${messageId}`, {
      body: JSON.stringify({ content, state: state ?? null }),
      method: 'PUT',
    }),

  updatePersona: (
    id: number,
    data: { avatar_path?: null | string; description?: string; name: string },
  ) =>
    request<{ ok: boolean }>(`/api/personas/${id}`, { body: JSON.stringify(data), method: 'PUT' }),

  // Avatar upload
  uploadAvatar: async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${apiBase()}/api/bots/upload/avatar`, {
      body: formData,
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const data = await res.json();
    return data.path;
  },
  // File upload
  uploadFile: async (threadId: number, botId: number, file: File): Promise<ThreadFileDTO> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${apiBase()}/api/threads/${threadId}/files?bot_id=${botId}`, {
      body: formData,
      method: 'POST',
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore parse errors */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },
  // Persona Avatar upload
  uploadPersonaAvatar: async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${apiBase()}/api/personas/upload/avatar`, {
      body: formData,
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const data = await res.json();
    return data.path;
  },
  // Validate an embedding endpoint (model + base_url + api_key) before saving
  validateEmbedding: (data: {
    embedding_api_key?: null | string;
    embedding_base_url?: null | string;
    embedding_model: string;
  }) =>
    request<{ ok: true }>('/api/config/validate-embedding', {
      body: JSON.stringify(data),
      method: 'POST',
    }),
};

/** Server discovery response (Tauri Android wrapper). */
export interface ServerInfo {
  url: string;
  version: string;
}

/** Response body when TTS is disabled (HTTP 503). */
export interface TTSDisabled {
  detail: string;
}

export interface TTSSynthesizeRequest {
  model?: null | string;
  /** 0.5 .. 2.0 — clamped by the server */
  speed?: number;
  text: string;
  voice_id?: null | string;
}

// ── TTS (text-to-speech) ─────────────────────────────────────────────
// Frontend-only types; the route and cache contract live server-side.

export interface TTSSynthesizeResponse {
  /** Always `/api/tts/audio/<cache_id>` (resolves against apiBase). */
  audio_url: string;
  /** 16-char hex cache id; the key the GET endpoint streams. */
  cache_id: string;
  /** True if this call hit the disk cache and skipped the provider. */
  from_cache: boolean;
}

/**
 * Probe a candidate server URL for the /api/server-info endpoint.
 * Used by ConnectToServer.svelte to validate a manually-entered
 * URL or a URL parsed from a QR code. Resolves with the parsed
 * ServerInfo on success; rejects with a descriptive error on
 * network failure or non-2xx response.
 */
export async function getServerInfo(candidateUrl: string): Promise<ServerInfo> {
  const base = candidateUrl.replace(/\/+$/, '');
  const res = await fetch(`${base}/api/server-info`);
  if (!res.ok) {
    throw new Error(`Server returned ${res.status}`);
  }
  const data = (await res.json()) as ServerInfo;
  if (typeof data.url !== 'string' || typeof data.version !== 'string') {
    throw new Error('Server response missing url or version');
  }
  return data;
}

/**
 * Open an SSE stream of reindex progress events for a given job.
 * Caller is responsible for `.close()`-ing the source when done.
 */
export function reindexEventSource(jobId: string): EventSource {
  return new EventSource(`${apiBase()}/api/config/knowledge/reindex/${jobId}/stream`);
}

export const ttsApi = {
  /** Absolute URL for a cached audio blob, suitable for ``<audio src="...">``. */
  audioUrl(cache_id: string): string {
    return `${apiBase()}/api/tts/audio/${cache_id}`;
  },

  /**
   * Synthesize text to speech. Returns a 16-char cache id that the
   * caller can fetch via ``audioFor(cache_id)`` (using the same
   * apiBase origin).
   *
   * Backend returns 503 when ``Settings.tts_provider == "disabled"``;
   * rethrow as a flagged error so callers can hide the play button.
   */
  async synthesize(req: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse> {
    const res = await fetch(`${apiBase()}/api/tts/synthesize`, {
      body: JSON.stringify(req),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    if (res.status === 503) {
      // Distinguish "disabled" from a real provider failure by
      // surfacing a typed error code; the UI uses this to hide the
      // play button instead of showing an error toast on every page.
      const body = (await res.json().catch(() => ({ detail: 'tts disabled' }))) as TTSDisabled;
      throw new TTSDisabledError(body.detail || 'TTS disabled');
    }
    if (!res.ok) {
      throw new Error(`TTS synthesize failed: ${res.status}`);
    }
    return (await res.json()) as TTSSynthesizeResponse;
  },
};

/** Thrown when the backend returns 503 because TTS is disabled. */
export class TTSDisabledError extends Error {
  override name = 'TTSDisabledError';
}
