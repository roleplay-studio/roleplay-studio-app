// _mocks/personaFixtures.ts — factory of Persona objects for demos that
// show persona selection. Uses the real Persona interface (4 fields:
// id, name, avatar_path, description). null avatars → gradient placeholder.

import type { Persona } from '../../../api';

const DATA: Persona[] = [
  { avatar_path: null, description: 'A weary wanderer seeking shelter.', id: 1, name: 'Traveler' },
  { avatar_path: null, description: 'Driven by curiosity and chance.', id: 2, name: 'Wanderer' },
  { avatar_path: null, description: 'Records tales of those she meets.', id: 3, name: 'Scribe' },
  {
    avatar_path: null,
    description: 'Bold, reckless, and lucky so far.',
    id: 4,
    name: 'Adventurer',
  },
];

export function mockPersonas(n = 3): Persona[] {
  return DATA.slice(0, n);
}
