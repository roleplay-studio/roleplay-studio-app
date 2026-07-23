/**
 * Pure sort / filter / search helpers for the Bots library page
 * (introduced by ``improve-bot-editor``).
 *
 * These are deliberately framework-free so they're trivial to unit-test
 * (see ``src/lib/__tests__/botsBrowse.test.ts``). The Svelte 5 wiring
 * happens in ``BotsPage.svelte`` via ``$derived(applyBotsFilters(...))``
 * — keeping derivation logic out of the components makes the contract
 * easy to pin and easy to reuse from the UI catalog.
 *
 * Sort dimensions are constrained to fields actually present on
 * ``BotResponse``: ``id``, ``name``, ``thread_count``. ``created_at``
 * is NOT exposed by the API and is intentionally absent — see
 * ``openspec/changes/improve-bot-editor/design.md`` Open Question Q1.
 */

import type { Bot, BotType } from './api';

export interface BotsFilterState {
  /** Substring match against ``name``. Empty / whitespace = no filter. */
  query: string;
  sortDir: BotSortDir;
  sortKey: BotSortKey;
  /** Multi-select type filter. Empty array means "no filter". */
  types: BotType[];
}
export type BotSortDir = 'asc' | 'desc';

export type BotSortKey = 'id' | 'name' | 'thread_count';

// One shared collator so we don't pay the construction cost on every
// keystroke. ``sensitivity: 'base'`` makes 'a' and 'A' tie (matches the
// usual UI expectation for a name column) and accents/diacritics are
// roughly equalised. jsdom and modern Chrome both honour this API.
const NAME_COLLATOR = new Intl.Collator(undefined, { sensitivity: 'base' });

/**
 * Composite: filter → search → sort. Order is deliberate:
 *
 *   1. filterByType reduces the working set the earliest.
 *   2. searchByName further narrows.
 *   3. sortBots orders the survivors.
 *
 * The resulting list is fresh — the input array is never mutated.
 * The component layer plugs this straight into ``$derived``.
 */
export function applyBotsFilters(bots: Bot[], state: BotsFilterState): Bot[] {
  const filtered = filterByType(bots, state.types);
  const searched = searchByName(filtered, state.query);
  return sortBots(searched, state.sortKey, state.sortDir);
}

/**
 * Keep only bots whose ``bot_type`` is in ``types``. Empty ``types``
 * means "no filter" — the original list comes through unchanged.
 * Multi-select uses logical OR (a bot survives if its type matches
 * ANY of the selected chips).
 */
export function filterByType(bots: Bot[], types: BotType[]): Bot[] {
  if (types.length === 0) return bots.slice();
  const allowed = new Set<BotType>(types);
  return bots.filter((b) => allowed.has(b.bot_type));
}

/**
 * Case-insensitive substring match against ``name``. Empty or
 * whitespace-only query short-circuits to "no filter".
 */
export function searchByName(bots: Bot[], query: string): Bot[] {
  const trimmed = query.trim();
  if (trimmed === '') return bots.slice();
  const needle = trimmed.toLowerCase();
  return bots.filter((b) => b.name.toLowerCase().includes(needle));
}

/**
 * Return a NEW array sorted by ``key`` in ``dir``. Never mutates
 * the input — the test suite pins this contract explicitly so the
 * Svelte 5 reactivity layer can rely on it without copy-on-write
 * gymnastics.
 */
export function sortBots(bots: Bot[], key: BotSortKey, dir: BotSortDir): Bot[] {
  const out = bots.slice();
  const cmp = compareByKey(key);
  // V8's Array.prototype.sort has been stable since Node 12, which
  // matches our baseline (see AGENTS.md §8).
  out.sort((a, b) => (dir === 'asc' ? cmp(a, b) : -cmp(a, b)));
  return out;
}

function compareByKey(key: BotSortKey): (a: Bot, b: Bot) => number {
  switch (key) {
    case 'id':
      return compareId;
    case 'name':
      return compareName;
    case 'thread_count':
      return compareThreadCount;
  }
}

function compareId(a: Bot, b: Bot): number {
  // Numeric compare on id (auto-increment, chronological proxy).
  return a.id - b.id;
}

function compareName(a: Bot, b: Bot): number {
  return NAME_COLLATOR.compare(a.name, b.name);
}

function compareThreadCount(a: Bot, b: Bot): number {
  return a.thread_count - b.thread_count;
}