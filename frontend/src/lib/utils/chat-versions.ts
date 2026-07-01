import type { Message } from '../api';

/**
 * Result of syncing the Chat.svelte versions state from a fresh
 * message list (typically returned by api.listMessages).
 *
 * `versions` is keyed by message id and contains ALL versions of
 * that branch group (active + inactive). `currentVersionIndex` is
 * keyed by the same id and contains the index of the currently
 * active version in the array, or 0 if none is active.
 */
export interface SyncedVersionsState {
  currentVersionIndex: Record<number, number>;
  versions: Record<number, Message[]>;
}

/**
 * Walks a list of messages (typically from api.listMessages) and
 * produces the per-message-id `versions` and `currentVersionIndex`
 * maps that Chat.svelte uses to render the ◀ N/M ▶ counter.
 *
 * Messages without embedded `versions` (unbranched) are skipped —
 * they do not get a counter, and their existing state entries (if
 * any) are not removed. (We return empty maps, never overwrite
 * caller state.)
 *
 * The output of this function should be spread into the existing
 * `versions` and `currentVersionIndex` state in Chat.svelte, e.g.:
 *
 *   const synced = syncVersionsStateFromMessages(messages);
 *   versions = { ...versions, ...synced.versions };
 *   currentVersionIndex = {
 *     ...currentVersionIndex,
 *     ...synced.currentVersionIndex,
 *   };
 *
 * This keeps the existing map semantics (spread, not assign) so
 * that messages not in the fresh list retain their state.
 */
export function syncVersionsStateFromMessages(messages: Message[]): SyncedVersionsState {
  const versions: Record<number, Message[]> = {};
  const currentVersionIndex: Record<number, number> = {};
  for (const m of messages) {
    if (m.id === null) continue;
    if (m.versions && m.versions.length > 0) {
      versions[m.id] = m.versions;
      const activeIdx = m.versions.findIndex((v) => v.is_active);
      currentVersionIndex[m.id] = activeIdx >= 0 ? activeIdx : 0;
    }
  }
  return { currentVersionIndex, versions };
}
