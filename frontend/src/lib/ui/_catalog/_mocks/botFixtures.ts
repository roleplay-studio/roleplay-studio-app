// _mocks/botFixtures.ts — factory of realistic Bot objects with null
// avatars so demos never hit the network. The Bot shape is verified
// against `frontend/src/lib/api.ts` (12 required fields).

import { type Bot, BOT_TYPES } from '../../../api';

const NAMES = ['Aria the Bard', 'Luna', 'Hermes', 'Scribe', 'Nova', 'Iris'];
const PERSONALITIES = [
  'curious, witty, slightly mischievous',
  'calm, patient, and observant',
  'ancient and wise, with a dry sense of humor',
  'eager, energetic, asks many questions',
  'melancholic poet, speaks in metaphors',
];
const SCENARIOS = [
  'A dimly lit tavern at the edge of the world.',
  'A bustling market square in the capital city.',
  'A misty forest path after a long rain.',
  "The captain's quarters aboard a star-faring vessel.",
  'A ruined library where dust motes dance in the light.',
];

export function mockBots(n = 3): Bot[] {
  return NAMES.slice(0, Math.min(n, NAMES.length)).map((name, i) => ({
    alternate_greetings: ['Greetings, friend.', 'Ah, a newcomer. Welcome.'],
    avatar_path: null, // null → gradient placeholder, no API call
    bot_type: BOT_TYPES[i % BOT_TYPES.length].value,
    categories: i % 2 === 0 ? ['fantasy', 'adventure'] : ['helper'],
    description: `${name} is a catalog demo bot with a slightly verbose description for visual balance.`,
    first_message: 'Hello, traveler!',
    id: i + 1,
    name,
    personality: PERSONALITIES[i % PERSONALITIES.length],
    scenario: SCENARIOS[i % SCENARIOS.length],
    thread_count: 3 + i * 2,
  }));
}
