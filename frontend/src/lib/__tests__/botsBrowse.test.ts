/** Tests for ``src/lib/botsBrowse.ts``.

Pins the contract of the Bots library sort/filter/search helpers
introduced by ``improve-bot-editor``. Mirrors the pattern from
``src/lib/utils/threadSort.test.ts`` (pure functions, no Svelte
runtime). The Svelte 5 wiring (``$derived``) is exercised through the
component tests in Phase 1.5+; this file locks the data-shape behaviour
the components depend on.

Sort dimensions are pinned to fields actually present on ``BotResponse``
(id, name, thread_count). ``created_at`` is NOT exposed in the API and
is intentionally absent — see design.md Open Question Q1.
*/

import { describe, expect, it } from 'vitest';

import type { Bot, BotType } from '../api';

import {
  applyBotsFilters,
  type BotSortDir,
  type BotSortKey,
  filterByType,
  searchByName,
  sortBots,
} from '../botsBrowse';

function bot(partial: Partial<Bot> & Pick<Bot, 'id' | 'name'>): Bot {
  return {
    alternate_greetings: [],
    avatar_path: null,
    bot_type: 'rp' as BotType,
    categories: [],
    categories_invalid: [],
    description: '',
    first_message: '',
    mes_example: '',
    name: '',
    personality: '',
    scenario: '',
    skills: [],
    skills_invalid: [],
    thread_count: 0,
    world_state_prompt: '',
    ...partial,
  };
}

// Hand-picked fixtures — 5 bots spanning all three bot_types so each
// describe() can combine them without rebuilding mocks.
const f = {
  alpha: bot({ bot_type: 'rp', id: 10, name: 'Alpha', thread_count: 3 }),
  bravo: bot({ bot_type: 'assistant', id: 5, name: 'Bravo', thread_count: 7 }),
  charlie: bot({ bot_type: 'rp', id: 8, name: 'Charlie', thread_count: 1 }),
  delta: bot({ bot_type: 'agent', id: 3, name: 'Delta', thread_count: 12 }),
  echo: bot({ bot_type: 'rp', id: 1, name: 'Echo', thread_count: 5 }),
};

describe('sortBots', () => {
  it('returns a new array (does not mutate input)', () => {
    const input = [f.alpha, f.bravo, f.charlie];
    const before = input.slice();
    sortBots(input, 'name', 'asc');
    expect(input).toEqual(before);
  });

  it('sorts by name asc using locale-aware comparison', () => {
    const out = sortBots([f.charlie, f.alpha, f.bravo], 'name', 'asc');
    expect(out.map((b) => b.name)).toEqual(['Alpha', 'Bravo', 'Charlie']);
  });

  it('sorts by name desc', () => {
    const out = sortBots([f.alpha, f.bravo, f.charlie], 'name', 'desc');
    expect(out.map((b) => b.name)).toEqual(['Charlie', 'Bravo', 'Alpha']);
  });

  it('sorts by id desc (chronological proxy for created_at — design.md Q1)', () => {
    // id desc => highest id first. With our fixtures [10, 5, 8, 3, 1]
    // that yields [Alpha(10), Charlie(8), Bravo(5), Delta(3), Echo(1)].
    const out = sortBots(
      [f.echo, f.delta, f.bravo, f.charlie, f.alpha],
      'id',
      'desc',
    );
    expect(out.map((b) => b.id)).toEqual([10, 8, 5, 3, 1]);
  });

  it('sorts by thread_count desc — heaviest threads first', () => {
    // thread_counts in input order: 3, 7, 1, 12, 5. Desc: 12, 7, 5, 3, 1.
    const out = sortBots(
      [f.alpha, f.bravo, f.charlie, f.delta, f.echo],
      'thread_count',
      'desc',
    );
    expect(out.map((b) => b.thread_count)).toEqual([12, 7, 5, 3, 1]);
  });

  it('is stable for equal keys (Array.prototype.sort stability)', () => {
    // Two bots with thread_count=0 must keep input order. We rely on
    // V8's stable sort, which jsdom's sort impl mirrors.
    const a = bot({ id: 1, name: 'A', thread_count: 0 });
    const b = bot({ id: 2, name: 'B', thread_count: 0 });
    const out = sortBots([a, b], 'thread_count', 'asc');
    expect(out.map((x) => x.id)).toEqual([1, 2]);
  });
});

describe('filterByType', () => {
  it('returns the original list when no types are selected', () => {
    const out = filterByType([f.alpha, f.bravo, f.delta], []);
    expect(out).toEqual([f.alpha, f.bravo, f.delta]);
  });

  it('returns only bots of the requested single type', () => {
    const out = filterByType([f.alpha, f.bravo, f.charlie], ['rp']);
    expect(out.map((b) => b.id)).toEqual([10, 8]); // Alpha + Charlie
  });

  it('combines multiple types with logical OR', () => {
    const out = filterByType(
      [f.alpha, f.bravo, f.charlie, f.delta, f.echo],
      ['assistant', 'agent'],
    );
    // Bravo (assistant) + Delta (agent)
    expect(out.map((b) => b.id).sort()).toEqual([3, 5]);
  });

  it('does not mutate the input array', () => {
    const input = [f.alpha, f.bravo];
    const before = input.slice();
    filterByType(input, ['rp']);
    expect(input).toEqual(before);
  });
});

describe('searchByName', () => {
  it('returns the original list when query is empty', () => {
    const out = searchByName([f.alpha, f.bravo, f.charlie], '');
    expect(out).toEqual([f.alpha, f.bravo, f.charlie]);
  });

  it('matches case-insensitive substring of the bot name', () => {
    const out = searchByName([f.alpha, f.bravo, f.charlie], 'bRa');
    expect(out.map((b) => b.id)).toEqual([5]); // Bravo only
  });

  it('returns empty array when no bot name contains the query', () => {
    const out = searchByName([f.alpha, f.bravo, f.charlie], 'zzz');
    expect(out).toEqual([]);
  });

  it('treats whitespace-only query as empty', () => {
    const out = searchByName([f.alpha, f.bravo], '   ');
    expect(out).toEqual([f.alpha, f.bravo]);
  });
});

describe('applyBotsFilters (composite)', () => {
  it('default state — id desc, no type filter, empty query — preserves order', () => {
    // Default direction is id desc, no filter, no search → effective
    // ordering is [10, 8, 5, 3, 1].
    const out = applyBotsFilters([f.echo, f.delta, f.bravo, f.charlie, f.alpha], {
      query: '',
      sortDir: 'desc' as BotSortDir,
      sortKey: 'id' as BotSortKey,
      types: [],
    });
    expect(out.map((b) => b.id)).toEqual([10, 8, 5, 3, 1]);
  });

  it('applies filter BEFORE search AND sort (logical AND across stages)', () => {
    // Stages: filter (types=[rp]) → search ("a") → sort (name asc).
    // After filter: Alpha, Charlie, Echo.
    // After search "a": Alpha (contains "a"? no — wait: Alpha contains
    // "a", yes), Charlie (contains "a"), Echo (no). Final: Alpha, Charlie.
    // After name asc: Alpha, Charlie.
    const out = applyBotsFilters(
      [f.echo, f.delta, f.bravo, f.charlie, f.alpha],
      {
        query: 'a',
        sortDir: 'asc',
        sortKey: 'name',
        types: ['rp'],
      },
    );
    expect(out.map((b) => b.id)).toEqual([10, 8]); // Alpha, Charlie
  });

  it('empty-state signal: yields [] when combined filters match nothing', () => {
    const out = applyBotsFilters([f.alpha, f.bravo, f.charlie], {
      query: 'zzz',
      sortDir: 'desc',
      sortKey: 'id',
      types: [],
    });
    expect(out).toEqual([]);
  });

  it('multi-type filter combines with name search via AND', () => {
    // types=[assistant, agent] + query="a"
    // After filter: Bravo (assistant), Delta (agent). Both contain "a".
    // After search: both survive. After name asc: Bravo, Delta.
    const out = applyBotsFilters([f.alpha, f.bravo, f.charlie, f.delta, f.echo], {
      query: 'a',
      sortDir: 'asc',
      sortKey: 'name',
      types: ['assistant', 'agent'],
    });
    expect(out.map((b) => b.id)).toEqual([5, 3]); // Bravo, Delta
  });

  it('input array is not mutated across any stage', () => {
    const input = [f.echo, f.delta, f.bravo, f.charlie, f.alpha];
    const before = input.slice();
    applyBotsFilters(input, {
      query: 'a',
      sortDir: 'asc',
      sortKey: 'name',
      types: ['rp'],
    });
    expect(input).toEqual(before);
  });
});