// _mocks/messageFixtures.ts — factory of Message objects for the
// MessageBubble demo. Uses the real Message interface (11 required
// fields; `is_active` and `short_content` are required, `versions`
// is `Message[]`). The last user message in the array has a 2-version
// branch to exercise the version-switcher UI in MessageBubble.

import type { Message } from '../../../api';

const NOW = Date.now();

export function mockMessages(n = 4): Message[] {
  const out: Message[] = [];
  for (let i = 0; i < n; i++) {
    const isUser = i % 2 === 0;
    const withVersions = i === n - 1 && isUser; // last user msg has versions
    out.push(makeMsg(i, isUser, withVersions));
  }
  return out;
}

function makeMsg(i: number, isUser: boolean, withVersions: boolean): Message {
  const content = isUser
    ? 'Hello! How are you today?'
    : 'Greetings, traveler! The road has been long, but I am glad to see a friendly face.';
  const edited = 'Hello! How are you today, my friend?';
  const createdAt = new Date(NOW - (4 - i) * 60_000).toISOString();

  if (!withVersions) {
    return {
      branch_group: null,
      branch_index: 0,
      content,
      created_at: createdAt,
      id: i + 1,
      is_active: true,
      role: isUser ? 'user' : 'assistant',
      short_content: content.slice(0, 80),
    };
  }

  // 2-version branch: v1 is the original (inactive), v2 is the edit (active)
  return {
    branch_group: 'bg-1',
    branch_index: 1,
    content: edited,
    created_at: createdAt,
    id: i + 1,
    is_active: true,
    role: 'user',
    short_content: edited.slice(0, 80),
    versions: [
      {
        branch_group: 'bg-1',
        branch_index: 0,
        content,
        created_at: new Date(NOW - 120_000).toISOString(),
        id: 100,
        is_active: false,
        role: 'user',
        short_content: content.slice(0, 80),
      },
      {
        branch_group: 'bg-1',
        branch_index: 1,
        content: edited,
        created_at: createdAt,
        id: 101,
        is_active: true,
        role: 'user',
        short_content: edited.slice(0, 80),
      },
    ],
  };
}
