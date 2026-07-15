/**
 * Chat-window settings — small user-facing toggles that should
 * persist across reloads but don't need a round-trip to the server.
 *
 * Mirrors the shape of ``theme.ts`` (shared module state + listener
 * notification). The Svelte 5 idiom for consumers is::
 *
 *     let autoplay = $state(getAutoplayTts());
 *     $effect(() => onChatSettingsChange(s => autoplay = s.autoplayTts));
 *
 * or, more cheaply for one knob, just call the setter and re-read::
 *
 *     setAutoplayTts(!current);
 *
 * Storage schema is versioned (``v1``) so we can evolve it later
 * without tripping over stale localStorage entries from older builds.
 */

const STORAGE_KEY = 'chat_settings_v1';

/** Single source of truth — extend when we add new toggles. */
export interface ChatSettings {
  /** Auto-play TTS for the most recent assistant message after a
   *  stream completes (send / regenerate / fork). */
  autoplayTts: boolean;
}

const DEFAULTS: ChatSettings = {
  autoplayTts: false,
};

let _current: ChatSettings = load() ?? { ...DEFAULTS };
let _listeners: Array<(s: ChatSettings) => void> = [];

function load(): ChatSettings | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Defensive merge — unknown keys are dropped, missing keys
    // fall back to defaults so a partial write doesn't break reads.
    return { ...DEFAULTS, ...parsed };
  } catch {
    // Corrupt JSON / quota / private mode — ignore and start clean.
    return null;
  }
}

function persist(s: ChatSettings) {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* localStorage may be unavailable; the in-memory copy still works. */
  }
}

function notify() {
  for (const fn of _listeners) fn(_current);
}

/** Read-only snapshot. */
export function getChatSettings(): ChatSettings {
  return _current;
}

export function getAutoplayTts(): boolean {
  return _current.autoplayTts;
}

export function setAutoplayTts(value: boolean): void {
  if (_current.autoplayTts === value) return;
  _current = { ..._current, autoplayTts: value };
  persist(_current);
  notify();
}

/** Bulk update — preferred when changing several toggles at once to
 *  avoid the cost (and listener spam) of N individual notifies. */
export function updateChatSettings(patch: Partial<ChatSettings>): void {
  const next = { ..._current, ...patch };
  if (JSON.stringify(next) === JSON.stringify(_current)) return;
  _current = next;
  persist(_current);
  notify();
}

/** Subscribe to changes. Returns an unsubscribe fn. */
export function onChatSettingsChange(fn: (s: ChatSettings) => void): () => void {
  _listeners.push(fn);
  // Fire once with the current value so callers can sync their
  // local $state on mount without a separate getter call.
  fn(_current);
  return () => {
    _listeners = _listeners.filter((l) => l !== fn);
  };
}