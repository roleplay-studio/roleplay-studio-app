const STORAGE_KEY = 'dismissed_notifications';

interface DismissedEntry {
  dismissedAt: number;
  text: string;
}

/** Clear all dismissed notification records */
export function clearDismissedNotifications(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** Mark notification as dismissed + clean entries older than 24h */
export function dismissNotification(text: string): void {
  const now = Date.now();
  const DAY_MS = 24 * 60 * 60 * 1000;
  const entries = load().filter((e) => now - e.dismissedAt < DAY_MS);
  entries.push({ dismissedAt: now, text });
  save(entries);
}

/** Was this notification already dismissed by the user? */
export function isNotificationDismissed(text: string): boolean {
  const entries = load();
  return entries.some((e) => e.text === text);
}

function load(): DismissedEntry[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function save(entries: DismissedEntry[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}
