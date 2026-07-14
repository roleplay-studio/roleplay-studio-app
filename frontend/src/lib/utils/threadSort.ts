/** Shared thread-sort logic used by Chat, Dashboard, and RecentChats.

The three callers all show a list of threads and want to give the user a
sort dropdown. The backend already returns threads in newest-activity-first
order via ``list_for_bot_with_preview`` / ``list_recent_with_previews``,
but the UI needs three user-selectable orderings:

- ``by-last-activity`` — the backend default. Newest message at top.
- ``by-message-count``  — most active first (great for "what's happening
  with this bot right now?"). Empty threads sink to the bottom.
- ``by-name``          — alphabetical ascending. Useful when the list
  is long and you want to find a specific title.

The pure helper takes the array and a mode, returns a NEW sorted array
(no in-place mutation). Svelte's $derived picks up on the new reference.

This module deliberately avoids Svelte runes so it can be imported from
non-component code (CLI scripts, tests). It returns plain arrays.

Design note: ``message_count`` defaults to 0 for legacy threads that
haven't been enriched yet — those threads sort alongside truly empty
threads at the *bottom* of by-message-count, which matches user
intent (browse the actively-chatting ones first).
*/

import type { RecentThread, Thread } from '../api';

/** User-selectable sort order. Add new modes here when the UI grows them. */
export type ThreadSortMode =
  /** Backend default — newest message first. */
  | 'by-last-activity'
  /** Most active first; empty threads at the bottom. */
  | 'by-message-count'
  /** Alphabetical by display name (case-insensitive locale-aware). */
  | 'by-name';

/** Display strings for the sort dropdown — kept here so i18n consumers
 * can re-use them in whichever format (label, tooltip, count-badge)
 * suits the surface. Keys are stable. */
export const THREAD_SORT_MODE_KEYS: Record<ThreadSortMode, string> = {
  'by-last-activity': 'thread_sort.by_last_activity',
  'by-message-count': 'thread_sort.by_message_count',
  'by-name': 'thread_sort.by_name',
};

/** Sort for the cross-bot listing (RecentChats / Dashboard fallback). */
export function sortRecentThreads(
  threads: RecentThread[],
  mode: ThreadSortMode,
): RecentThread[] {
  const next = [...threads];
  switch (mode) {
    case 'by-last-activity': {
      next.sort((a, b) => {
        const ta = a.last_message_at ? Date.parse(a.last_message_at) : 0;
        const tb = b.last_message_at ? Date.parse(b.last_message_at) : 0;
        if (ta !== tb) return tb - ta;
        return (b.last_message_short_content?.length ?? 0) -
          (a.last_message_short_content?.length ?? 0);
      });
      break;
    }
    case 'by-message-count':
      next.sort((a, b) => {
        if (a.message_count !== b.message_count) return b.message_count - a.message_count;
        const ta = a.last_message_at ? Date.parse(a.last_message_at) : 0;
        const tb = b.last_message_at ? Date.parse(b.last_message_at) : 0;
        return tb - ta;
      });
      break;
    case 'by-name':
      // Cross-bot uses ``bot_name`` as the primary sort key, then persona.
      next.sort((a, b) => {
        const byBot = a.bot_name.localeCompare(b.bot_name, undefined, {
          sensitivity: 'base',
        });
        if (byBot !== 0) return byBot;
        return (a.persona_name ?? '').localeCompare(b.persona_name ?? '', undefined, {
          sensitivity: 'base',
        });
      });
      break;
  }
  return next;
}

/** Sort for the per-bot listing (Drawer's threadList rows). */
export function sortThreads(
  threads: Thread[],
  mode: ThreadSortMode,
): Thread[] {
  const next = [...threads];
  switch (mode) {
    case 'by-last-activity': {
      next.sort((a, b) => {
        // Stable contract: NULL last_message_at sinks below real ones
        // (created_at is a fine tiebreaker because the backend keys
        // off it for empty-thread ordering).
        const ta = a.last_message_at ? Date.parse(a.last_message_at) : 0;
        const tb = b.last_message_at ? Date.parse(b.last_message_at) : 0;
        if (ta !== tb) return tb - ta;
        return (b.created_at ? Date.parse(b.created_at) : 0) -
          (a.created_at ? Date.parse(a.created_at) : 0);
      });
      break;
    }
    case 'by-message-count':
      next.sort((a, b) => {
        if (a.message_count !== b.message_count) return b.message_count - a.message_count;
        // Stable tiebreaker by activity.
        const ta = a.last_message_at ? Date.parse(a.last_message_at) : 0;
        const tb = b.last_message_at ? Date.parse(b.last_message_at) : 0;
        return tb - ta;
      });
      break;
    case 'by-name':
      next.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
      break;
  }
  return next;
}
