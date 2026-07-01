/**
 * Regression test for the exact UX bug Dima reported:
 *
 * > "при изменении сообщения, старое стало не активным а новое не появилось,
 * >  и нарушилась последовательность сообщений"
 *
 * Repro in 3 steps:
 *  1. User edits a user message (the right-click → Edit flow).
 *  2. Frontend calls `api.updateMessage` → backend creates a new branch,
 *     deactivates the original, embeds `versions: [v0, v1]` in the
 *     refetched list.
 *  3. Frontend must re-derive `versions` state for the new id and pass
 *     it to `MessageBubble`, otherwise the bubble renders WITHOUT the
 *     ◀ N/M ▶ counter and the user sees a "broken sequence" because
 *     the new bubble is shown but the old one looks deactivated
 *     (no counter on it = indistinguishable from a missing bubble).
 *
 * The fix lives in two places:
 *   - `frontend/src/lib/utils/chat-versions.ts::syncVersionsStateFromMessages`
 *     — pure helper that walks `messages` and produces the per-id
 *     `versions` map.
 *   - `frontend/src/lib/pages/Chat.svelte::saveEditModal` — calls the
 *     helper after `api.listMessages`.
 *
 * This test simulates the end-to-end UI flow: build a fresh `messages`
 * list as it would come back from the backend, run it through the
 * helper, then pass the resulting `versions[id]` to `MessageBubble`.
 * If `syncVersionsStateFromMessages` is broken, the bubble renders
 * without the counter — that's the bug, frozen in a test.
 */

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import type { Message } from '../api';

import MessageBubble from '../MessageBubble.svelte';
import { syncVersionsStateFromMessages } from '../utils/chat-versions';

function makeMessage(
  id: null | number,
  role: 'assistant' | 'user',
  content: string,
  versions: Message[] = [],
  isActive = true,
): Message {
  return {
    branch_group: versions.length > 0 ? `bg-${id}` : null,
    branch_index: 0,
    content,
    created_at: null,
    id,
    is_active: isActive,
    reasoning: '',
    role,
    short_content: '',
    versions,
  };
}

const baseProps = {
  botName: 'B',
  isLast: false,
  lang: 'en' as const,
  personaName: 'U',
};

afterEach(cleanup);

describe('User message edit → version counter end-to-end', () => {
  it('after editing a user message, the new bubble shows the version counter', () => {
    // ── 1. Backend state after `api.updateMessage(threadId, 5, "new text")`:
    //
    //    Original (id=5)  → is_active=False, branch_index=0
    //    Edited   (id=99) → is_active=True,  branch_index=1
    //    Both share branch_group="bg-99" (the new message's id is the
    //    canonical branch anchor per the backend contract).
    //
    //    `api.listMessages` returns the active messages only (SQL filter
    //    ``branch_group IS NULL OR is_active == true``), so the list
    //    contains the *new* message id=99, NOT the original id=5. The
    //    original is folded into `msg.versions`.
    const v0 = { ...makeMessage(5, 'user', 'original text', [], false), is_active: false };
    const v1 = makeMessage(99, 'user', 'new text', [], true);
    const editedMsg = {
      ...makeMessage(99, 'user', 'new text', [v0, v1], true),
    };
    const freshList: Message[] = [editedMsg];

    // ── 2. Frontend syncs versions state ──
    const synced = syncVersionsStateFromMessages(freshList);
    expect(synced.versions[99]).toEqual([v0, v1]);
    expect(synced.currentVersionIndex[99]).toBe(1); // v1 (new) is active

    // ── 3. The Chat.svelte render path passes versions[msg.id] to
    //    MessageBubble. If `synced.versions[99]` is empty, the bubble
    //    renders without the counter and the user sees a "broken
    //    sequence" (the new content is there, but the old is not
    //    visually accounted for, and the counter that would explain
    //    it is missing). That's the exact bug Dima hit.
    const bubbleVersions = synced.versions[99] ?? [];
    expect(bubbleVersions.length).toBe(2);

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: editedMsg,
        onedit: () => {},
        onswitchversion: () => {},
        versions: bubbleVersions,
      },
    });

    // ◀ 2/2 ▶ — both the original (inactive) and the edit (active) are
    // accounted for. v1 is active, so the counter shows "2/2".
    expect(screen.getByText('2/2')).toBeTruthy();
  });

  it('after editing an assistant message, the new bubble also shows the counter', () => {
    // Same contract on the assistant side. Mirrors the first test so a
    // future regression on one role can't silently break the other.
    const v0 = { ...makeMessage(5, 'assistant', 'first reply', [], false), is_active: false };
    const v1 = makeMessage(99, 'assistant', 'second reply', [], true);
    const editedMsg = makeMessage(99, 'assistant', 'second reply', [v0, v1], true);

    const synced = syncVersionsStateFromMessages([editedMsg]);
    const bubbleVersions = synced.versions[99] ?? [];

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: editedMsg,
        onedit: () => {},
        onregenerate: () => {},
        onswitchversion: () => {},
        versions: bubbleVersions,
      },
    });

    expect(screen.getByText('2/2')).toBeTruthy();
  });

  it('counter reflects the *correct* active version after multiple edits', () => {
    // Three edits: v0 (original) inactive, v1 inactive, v2 active.
    // Counter must show "3/3" with v2 as the current — not "1/3".
    const v0 = { ...makeMessage(5, 'user', 'v0', [], false), is_active: false };
    const v1 = { ...makeMessage(98, 'user', 'v1', [], false), is_active: false };
    const v2 = makeMessage(99, 'user', 'v2', [], true);
    const editedMsg = makeMessage(99, 'user', 'v2', [v0, v1, v2], true);

    const synced = syncVersionsStateFromMessages([editedMsg]);
    expect(synced.currentVersionIndex[99]).toBe(2);

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: editedMsg,
        onedit: () => {},
        onswitchversion: () => {},
        versions: synced.versions[99] ?? [],
      },
    });

    expect(screen.getByText('3/3')).toBeTruthy();
  });

  it('counter is NOT shown for a message that was never edited', () => {
    // A regular, unbranched message: the list contains it with
    // `versions: []`. The helper does NOT add an entry, so the
    // bubble receives `[]` and the counter must stay hidden.
    const plain = makeMessage(7, 'user', 'never edited', [], true);

    const synced = syncVersionsStateFromMessages([plain]);
    expect(synced.versions[7]).toBeUndefined();
    expect(synced.currentVersionIndex[7]).toBeUndefined();

    const { container } = render(MessageBubble, {
      props: {
        ...baseProps,
        msg: plain,
        onedit: () => {},
        versions: synced.versions[7] ?? [],
      },
    });

    expect(container.querySelector('.mb-versions')).toBeNull();
  });

  it('counter is NOT shown when an edit fails to embed versions (defensive)', () => {
    // Defensive case: backend returns the message with `versions: []`
    // even though it has a `branch_group` (shouldn't happen, but the
    // helper and component must not crash and must not render a
    // misleading "1/1" counter).
    const bogus = makeMessage(99, 'user', 'edited', [], true);
    bogus.branch_group = 'bg-99';

    const synced = syncVersionsStateFromMessages([bogus]);
    expect(synced.versions[99]).toBeUndefined();

    const { container } = render(MessageBubble, {
      props: {
        ...baseProps,
        msg: bogus,
        onedit: () => {},
        versions: synced.versions[99] ?? [],
      },
    });

    expect(container.querySelector('.mb-versions')).toBeNull();
  });
});
