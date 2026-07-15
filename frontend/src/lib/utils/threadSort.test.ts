/** Tests for ``src/lib/utils/threadSort.ts``.

The threadList feature (commits ``e666968``, ``thread-group-by-bot``)
introduced sortRecentThreads / sortThreads / groupThreadsByBot as pure
helpers. They get exercised through RecentChats / ThreadDrawer, but
that's an integration surface — at this level we lock the contract
(sort stability, group keying, by-name interaction, empty-input safety)
without standing up the full Svelte runtime.

Group-by-bot ordering rules this file pins down:
- Within-group order: by the active sortMode (by-last-activity /
  by-message-count / by-name).
- Across-group order: always by the group's most-recent
  last_message_at, descending. The sortMode does NOT change
  which group leads.
- Bots with zero threads after collapsing the input are dropped
  (Map.set only registers bot_ids that have at least one thread).
*/

import { describe, expect, it } from 'vitest';

import type { RecentThread } from '../api';
import type { ThreadSortMode } from './threadSort';

import {
  groupThreadsByBot,
  sortRecentThreads,
  sortThreads,
  THREAD_SORT_MODE_KEYS,
} from './threadSort';

function thread(
  partial: Partial<RecentThread> &
    Pick<RecentThread, 'bot_id' | 'bot_name' | 'thread_id'>,
): RecentThread {
  return {
    bot_avatar_path: null,
    bot_categories: [],
    bot_personality: '',
    last_message_at: null,
    last_message_preview: '',
    last_message_short_content: null,
    message_count: 0,
    persona_avatar_path: null,
    persona_name: null,
    summary: null,
    ...partial,
  };
}

const t = (id: number, botId: number, daysAgo: number, count: number) =>
  thread({
    bot_id: botId,
    bot_name: botId === 1 ? 'Asha' : 'Misha',
    last_message_at: new Date(Date.now() - daysAgo * 86_400_000).toISOString(),
    message_count: count,
    persona_name: `Persona-${id}`,
    thread_id: id,
  });

describe('THREAD_SORT_MODE_KEYS', () => {
  it('exports exactly three modes with stable i18n keys', () => {
    expect(Object.keys(THREAD_SORT_MODE_KEYS).sort()).toEqual([
      'by-last-activity',
      'by-message-count',
      'by-name',
    ]);
    expect(THREAD_SORT_MODE_KEYS['by-last-activity']).toBe('thread_sort.by_last_activity');
    expect(THREAD_SORT_MODE_KEYS['by-message-count']).toBe('thread_sort.by_message_count');
    expect(THREAD_SORT_MODE_KEYS['by-name']).toBe('thread_sort.by_name');
  });
});

describe('sortRecentThreads', () => {
  it('returns a new array (does not mutate input)', () => {
    const input = [t(1, 1, 5, 1), t(2, 1, 1, 5), t(3, 2, 10, 0)];
    const before = input.slice();
    sortRecentThreads(input, 'by-last-activity');
    expect(input).toEqual(before);
  });

  it('sorts by-last-activity: newest first, ties broken by short_content length DESC', () => {
    const a = t(1, 1, 5, 1); // 5 days ago, no short_content
    const b = t(2, 1, 1, 5); // 1 day ago — newest, leads regardless
    const c = t(3, 2, 5, 1); // 5 days ago — same age as `a`, will tiebreak
    c.last_message_short_content = 'this is the longer string than a';
    const out = sortRecentThreads([a, b, c], 'by-last-activity');
    // Order: b (newest) → c (longer tiebreak) → a (no content).
    expect(out.map((x) => x.thread_id)).toEqual([2, 3, 1]);
  });

  it('sorts by-message-count: highest first, ties broken by recent activity', () => {
    const a = t(1, 1, 5, 1);
    const b = t(2, 1, 10, 5); // newer but fewer messages
    const c = t(3, 2, 1, 5); // newer still, tied count
    const out = sortRecentThreads([a, b, c], 'by-message-count');
    // c and b tied on count(5); c is newer → wins tiebreak
    expect(out.map((x) => x.thread_id)).toEqual([3, 2, 1]);
  });

  it('sorts by-name: bot_name primary, persona_name secondary', () => {
    const a = thread({
      bot_id: 1,
      bot_name: 'Bravo',
      persona_name: 'Z',
      thread_id: 10,
    });
    const b = thread({
      bot_id: 1,
      bot_name: 'Alpha',
      persona_name: 'B',
      thread_id: 11,
    });
    const c = thread({
      bot_id: 1,
      bot_name: 'Alpha',
      persona_name: 'A',
      thread_id: 12,
    });
    const out = sortRecentThreads([a, b, c], 'by-name');
    expect(out.map((x) => x.thread_id)).toEqual([12, 11, 10]);
  });
});

describe('groupThreadsByBot', () => {
  it('returns [] for empty input', () => {
    expect(groupThreadsByBot([], 'by-last-activity')).toEqual([]);
  });

  it('drops bot_ids that have no threads in the input', () => {
    // Even though the only data is for bot_id=1, the helper must
    // not leak through a phantom empty group for bot_id=2.
    const input = [t(1, 1, 1, 5)];
    const out = groupThreadsByBot(input, 'by-last-activity');
    expect(out.map((g) => g.bot_id)).toEqual([1]);
  });

  it('orders groups by newest last_message_at DESC regardless of sortMode', () => {
    // Bot A's newest thread is 1 day ago, Bot B's newest is 0 days ago.
    // In all three sortModes the *group* ordering should put B first
    // because B has the more recent activity.
    const a = t(1, 1, 1, 100); // Bot A — recent but few users
    const b = t(2, 2, 0, 5); // Bot B — much newer, fewer messages
    const a2 = t(3, 1, 10, 100); // another thread for A, much older
    const modes: ThreadSortMode[] = ['by-last-activity', 'by-message-count', 'by-name'];
    for (const mode of modes) {
      const out = groupThreadsByBot([a, b, a2], mode);
      expect(out.map((g) => g.bot_id)).toEqual([2, 1]);
    }
  });

  it('orders threads WITHIN a group by the active sortMode', () => {
    // For by-message-count: thread with count=10 should beat thread
    // with count=1 within the same bot, regardless of activity.
    const olderButBigger = t(1, 1, 10, 10);
    const newerButSmaller = t(2, 1, 1, 1);
    const out = groupThreadsByBot([olderButBigger, newerButSmaller], 'by-message-count');
    expect(out).toHaveLength(1);
    expect(out[0].threads.map((x) => x.thread_id)).toEqual([1, 2]);
  });

  it('preserves bot metadata (avatar, categories) per group', () => {
    const a = thread({
      bot_avatar_path: '/static/avatars/asha.png',
      bot_categories: ['Helper', 'Anime'],
      bot_id: 1,
      bot_name: 'Asha',
      thread_id: 1,
    });
    const out = groupThreadsByBot([a], 'by-last-activity');
    expect(out[0].bot_avatar_path).toBe('/static/avatars/asha.png');
    expect(out[0].bot_categories).toEqual(['Helper', 'Anime']);
  });

  it('group-level lastActivityAt tracks the most-recent thread', () => {
    const a1 = t(1, 1, 5, 1); // 5 days ago
    const a2 = t(2, 1, 1, 1); // 1 day ago
    const a3 = t(3, 1, 10, 1); // 10 days ago
    const out = groupThreadsByBot([a1, a2, a3], 'by-last-activity');
    expect(out[0].lastActivityAt).toBe(a2.last_message_at);
  });
});

// ``sortThreads`` (ThreadDrawer path, per-bot) is a sibling helper
// with the same shape. Sanity-check it so future regressions are
// caught even if RecentChats changes its own path.
describe('sortThreads', () => {
  it('sorts by-last-activity for per-bot listing', () => {
    const a = t(1, 1, 5, 1);
    const b = t(2, 1, 1, 1);
    const out = sortThreads(
      [
        { ...a, name: 'older', parent_thread_id: null },
        { ...b, name: 'newer', parent_thread_id: null },
      ],
      'by-last-activity',
    );
    expect(out.map((x) => x.name)).toEqual(['newer', 'older']);
  });
});
