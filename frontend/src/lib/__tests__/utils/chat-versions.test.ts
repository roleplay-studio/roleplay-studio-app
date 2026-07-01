import { describe, expect, it } from 'vitest';

import type { Message } from '../../api';

import { syncVersionsStateFromMessages } from '../../utils/chat-versions';

function msg(
  role: 'assistant' | 'system' | 'user',
  id: null | number,
  content = '',
  versions: Message[] = [],
): Message {
  return {
    branch_group: null,
    branch_index: 0,
    content,
    created_at: null,
    id,
    is_active: true,
    reasoning: '',
    role,
    short_content: '',
    versions,
  };
}

describe('syncVersionsStateFromMessages', () => {
  it('populates versions state from messages that have embedded versions', () => {
    // Two versions of a user message (original + edit). v1 is the
    // now-inactive original (id matches the branchedMsg's id 10),
    // v2 is the active edit.
    const v1 = { ...msg('user', 10, 'original', []), is_active: false };
    const v2 = { ...msg('user', 11, 'edited', []), is_active: true };
    // The "active" message in the list — its id is 10 (matches v1),
    // its versions array contains both v1 (inactive) and v2 (active).
    const branchedMsg = msg('user', 10, 'edited', [v1, v2]);

    const { currentVersionIndex, versions } = syncVersionsStateFromMessages([branchedMsg]);

    // Versions are keyed by the parent's id (10), containing both versions.
    expect(versions[10]).toEqual([v1, v2]);
    // v2 is active, so its index in the versions array (1) is the
    // current version.
    expect(currentVersionIndex[10]).toBe(1);
  });

  it('skips messages with no embedded versions (unbranched)', () => {
    // Unbranched message: versions array is empty.
    const unbranched = msg('assistant', 5, 'plain reply', []);

    const { currentVersionIndex, versions } = syncVersionsStateFromMessages([unbranched]);

    // The helper does not add entries for unbranched messages.
    expect(versions).toEqual({});
    expect(currentVersionIndex).toEqual({});
  });

  it('falls back to index 0 when no version is active', () => {
    // Edge case: backend has not yet set is_active=True on the edit
    // (data race, partial commit, etc.). The helper should still
    // produce a usable index so the counter renders something
    // reasonable.
    const v1 = msg('user', 10, 'original', []);
    const v2 = { ...msg('user', 11, 'edited', []), is_active: false };
    const branchedMsg = msg('user', 10, 'original', [v1, v2]);

    const { currentVersionIndex } = syncVersionsStateFromMessages([branchedMsg]);

    expect(currentVersionIndex[10]).toBe(0);
  });
});
