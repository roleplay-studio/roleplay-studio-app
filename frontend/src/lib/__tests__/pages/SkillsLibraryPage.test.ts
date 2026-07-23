/**
 * Unit tests for SkillsLibraryPage.filterSkills.
 *
 * The page component has heavy UI dependencies (Modal, Card,
 * Button, Button slots) that are tricky to mount in jsdom without
 * introducing test flake. The pure filter logic is the only
 * piece that benefits from unit coverage; the rest is exercised
 * manually via browser smoke tests.
 *
 * Mirrors backend semantics (api.listSkills(q=..., tag=...)):
 * - q: case-insensitive substring against name + description
 * - tags: empty → all; non-empty → skill must have at least one
 *   tag in the selected set (OR semantics).
 */
import { describe, expect, it } from 'vitest';

import type { SkillDTO } from '../../api';

import { filterSkills } from '../../utils/filterSkills';

const skill = (
  id: number,
  name: string,
  description: string,
  tags: string[]
): SkillDTO => ({
  created_at: '2026-07-17T00:00:00Z',
  description,
  id,
  instruction: 'do the thing',
  name,
  tags,
  updated_at: '2026-07-17T00:00:00Z',
});

const LIBRARY: SkillDTO[] = [
  skill(1, 'Sarcastic', 'dry wit', ['tone', 'dialog']),
  skill(2, 'Concise', 'short replies', ['tone']),
  skill(3, 'Code Reviewer', 'review code line by line', ['code', 'technical']),
  skill(4, 'NPC Dialog', 'stay in character', ['rp', 'character']),
];

describe('filterSkills', () => {
  it('returns all skills when both q and tags are empty', () => {
    expect(filterSkills(LIBRARY, '', [])).toHaveLength(4);
  });

  it('matches by name substring (case-insensitive)', () => {
    const got = filterSkills(LIBRARY, 'CONCISE', []);
    expect(got).toHaveLength(1);
    expect(got[0].name).toBe('Concise');
  });

  it('matches by description substring (case-insensitive)', () => {
    const got = filterSkills(LIBRARY, 'review code', []);
    expect(got).toHaveLength(1);
    expect(got[0].name).toBe('Code Reviewer');
  });

  it('ignores leading and trailing whitespace in q', () => {
    const got = filterSkills(LIBRARY, '   Sarcastic   ', []);
    expect(got).toHaveLength(1);
    expect(got[0].name).toBe('Sarcastic');
  });

  it('combines q + tags with AND semantics for q then OR for tags', () => {
    // "sarcastic" matches name; tag "tone" matches both Sarcastic and Concise.
    // → intersect name-match with tag-match → just Sarcastic.
    const got = filterSkills(LIBRARY, 'sarcastic', ['tone']);
    expect(got).toHaveLength(1);
    expect(got[0].name).toBe('Sarcastic');
  });

  it('uses OR semantics for multiple tags', () => {
    const got = filterSkills(LIBRARY, '', ['code', 'rp']);
    expect(got.map((s) => s.name).sort()).toEqual(['Code Reviewer', 'NPC Dialog']);
  });

  it('matches tags case-insensitively', () => {
    const got = filterSkills(LIBRARY, '', ['TONE']);
    expect(got.map((s) => s.name).sort()).toEqual(['Concise', 'Sarcastic']);
  });

  it('returns empty when no skill matches the query', () => {
    expect(filterSkills(LIBRARY, 'no-such-thing', [])).toEqual([]);
  });

  it('handles empty library', () => {
    expect(filterSkills([], '', [])).toEqual([]);
    expect(filterSkills([], 'anything', ['anything'])).toEqual([]);
  });
});