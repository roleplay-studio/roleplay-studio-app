// _mocks/threadFixtures.ts — factory of RecentThread and Thread
// objects with realistic timestamps spread across 5 min / 1 hr / 1 day /
// 2 days / 1 week ago. The RecentThread shape is verified against
// api.ts (12 required fields; note: `last_message_preview` is a
// non-null string — use "" to mean "no preview" instead of null).

import type { RecentThread, Thread } from '../../../api';

const NAMES = ['Aria', 'Luna', 'Hermes', 'Scribe', 'Nova'];
const PERSONAS = ['Traveler', 'Wanderer', null, 'Scribe', 'Adventurer'];
const PERSONALITIES = [
  'curious, witty',
  'calm and patient',
  'ancient and wise',
  'eager, energetic',
  'melancholic poet',
];
const OFFSETS_MS = [300_000, 3_600_000, 86_400_000, 172_800_000, 604_800_000];
const PREVIEWS: (null | string)[] = [
  null,
  'I think we should rest here for the night before continuing the journey.',
  'The merchant offered us a fair price for the ring.',
  '', // empty string = no preview
  'See you next time!',
];
const SUMMARIES: (null | string)[] = [
  null,
  null,
  null,
  'A short summary of our last adventure together — the party rested at the inn.',
  null,
];

/** Mock `Thread[]` — used by ThreadDrawer (right aside in chat).
 *  7 required fields: bot_id, created_at, id, name, persona_id,
 *  persona_name, summary. */
export function mockChatThreads(n = 5): Thread[] {
  return Array.from({ length: n }, (_, i) => ({
    bot_id: (i % 3) + 1,
    created_at: new Date(Date.now() - OFFSETS_MS[i]).toISOString(),
    id: i + 1,
    name: `Chat with ${NAMES[i]}`,
    persona_id: PERSONAS[i] ? (i % 4) + 1 : null,
    persona_name: PERSONAS[i],
    summary: SUMMARIES[i],
  }));
}

/** Mock `RecentThread[]` — used by RecentChats (Recent Threads page).
 *  12 required fields, `last_message_preview` is a string (not null). */
export function mockRecentThreads(n = 5): RecentThread[] {
  return Array.from({ length: n }, (_, i) => ({
    bot_avatar_path: null,
    bot_categories: i % 2 === 0 ? ['fantasy'] : ['helper'],
    bot_id: (i % 3) + 1,
    bot_name: NAMES[i],
    bot_personality: PERSONALITIES[i],
    last_message_at: new Date(Date.now() - OFFSETS_MS[i]).toISOString(),
    last_message_preview: PREVIEWS[i] ?? '',
    persona_avatar_path: null,
    persona_name: PERSONAS[i],
    summary: SUMMARIES[i],
    thread_id: i + 1,
  }));
}

/** Back-compat alias — some demos use `mockThreads()` for both shapes. */
export function mockThreads(n = 5): RecentThread[] {
  return mockRecentThreads(n);
}
