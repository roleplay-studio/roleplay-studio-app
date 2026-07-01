/**
 * Theme management — light/dark/system.
 *
 * Preference is stored in localStorage and synced to the server.
 * On startup, localStorage wins (instant), server config is fallback.
 */

const STORAGE_KEY = 'theme_preference';

// Shared reactive state for SettingsPage
let _listeners: Array<(pref: string) => void> = [];
let _currentPref: string = getStored() || 'system';

/** Apply a resolved theme (dark/light) to the DOM. */
export function applyResolvedTheme(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark);
}

/** Apply a preference and save it. */
export function applyThemePreference(pref: string): void {
  _currentPref = pref;
  try {
    localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    /* ignore */
  }
  applyResolvedTheme(resolveTheme(pref));
  notify();
}

/** Get the current preference without resolving. */
export function getThemePreference(): string {
  return _currentPref;
}

/**
 * Initialize theme on app startup.
 * 1. localStorage (instant)
 * 2. If "system", set up matchMedia listener
 * 3. Returns the preference for server sync
 */
export function initTheme(): string {
  const stored = getStored();
  const pref = stored || 'system';
  _currentPref = pref;

  applyResolvedTheme(resolveTheme(pref));

  // Listen for system changes
  if (pref === 'system') {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => applyResolvedTheme(e.matches);
    mq.addEventListener('change', handler);
  }

  return pref;
}

/** Subscribe to preference changes. Returns unsubscribe function. */
export function onThemeChange(fn: (pref: string) => void): () => void {
  _listeners.push(fn);
  return () => {
    _listeners = _listeners.filter((l) => l !== fn);
  };
}

/** Resolve a preference to an actual dark/light boolean. */
export function resolveTheme(pref: string): boolean {
  if (pref === 'dark') return true;
  if (pref === 'light') return false;
  // system
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function getStored(): null | string {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function notify() {
  for (const fn of _listeners) fn(_currentPref);
}
