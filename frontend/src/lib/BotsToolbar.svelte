<!--
  BotsToolbar — sort / type-filter / name-search controls for the
  Bots library page. Introduced by ``improve-bot-editor``.

  Domain-aware composite component (knows about BotType / BotSortKey /
  BotSortDir). Lives in src/lib/, not src/lib/ui/ — same split as
  SkillPicker / CategoryPicker.

  Controlled component: no internal state. All values flow in via
  props; all user input flows out via callbacks. The parent
  (BotsPage) owns the $state and feeds it through botsBrowse helpers.

  Reuses existing primitives per AGENTS.md §5 + design D4:
  - <Select>  for the sort dimension+direction picker
  - <Badge>   for the type-filter chips (one per BotType in BOT_TYPES)
  - <Input>   for the name search field
  - <button>  wrapper for keyboard a11y on every chip

  Visual contract:
  - Each chip has class `bots-toolbar-chip min-h-11` — the latter is
    the mobile touch-target utility (DESIGN.md §Do's and Don'ts +
    MOBILE_PLAN.md Phase 4.5; ≥44×44px tap area on phone viewports).
  - Active chip carries `aria-pressed="true"` so screen readers
    announce the toggle state.
  - The "Clear all" affordance appears only when ≥1 chip is active,
    to keep the toolbar visually calm at the empty-filter default.

  No HTML `title=` for tooltips (banned per DESIGN.md) — chip overflow
  descriptions belong to <Tooltip>, not implemented in v1 (chips have
  enough room for the label on every supported viewport).
-->

<script lang="ts">
  import { SvelteSet } from 'svelte/reactivity';

  import type { BotSortDir, BotSortKey } from './botsBrowse';

  import { BOT_TYPES, type BotType } from './api';
  import { currentLang, t } from './i18n';
  import { Badge, Input, Select } from './ui';

  let {
    activeTypes = [],
    onqueryChange,
    onsortChange,
    ontypesChange,
    query = '',
    sortDir = 'desc',
    sortKey = 'id',
  }: {
    activeTypes?: BotType[];
    onqueryChange?: (query: string) => void;
    onsortChange?: (key: BotSortKey, dir: BotSortDir) => void;
    ontypesChange?: (types: BotType[]) => void;
    query?: string;
    sortDir?: BotSortDir;
    sortKey?: BotSortKey;
  } = $props();

  const lang = currentLang;

  // Sort options: 3 keys × 2 directions = 6 entries. Value format
  // is "<key>:<dir>" so the <Select> stays a thin string-keyed
  // component without needing to know about our enum pair.
  const SORT_OPTIONS: Array<{ label: string; value: string }> = [
    { label: t('bot_library.sort_name_asc', $lang), value: 'name:asc' },
    { label: t('bot_library.sort_name_desc', $lang), value: 'name:desc' },
    { label: t('bot_library.sort_id_desc', $lang), value: 'id:desc' },
    { label: t('bot_library.sort_id_asc', $lang), value: 'id:asc' },
    { label: t('bot_library.sort_threads_desc', $lang), value: 'thread_count:desc' },
  ];

  // ``sortValue`` must be $state, NOT $derived, because the Select
  // component uses ``bind:value`` and writes back to it on user
  // interaction. We pair it with an $effect that syncs the prop
  // changes from the parent (sortKey / sortDir) back into the local
  // string form ``"<key>:<dir>"``. We deliberately do NOT emit
  // onsortChange from this effect — emitting on mount would confuse
  // parents that initialise their own state from defaults.
  // svelte-ignore state_referenced_locally
  // eslint-disable-next-line svelte/prefer-writable-derived
  let sortValue = $state(`${sortKey}:${sortDir}`);

  $effect(() => {
    sortValue = `${sortKey}:${sortDir}`;
  });

  function handleSortChange() {
    // ``sortValue`` is updated by ``<Select bind:value>`` BEFORE this
    // callback fires, so we read the post-update value here.
    const [key, dir] = sortValue.split(':') as [BotSortKey, BotSortDir];
    onsortChange?.(key, dir);
  }

  function toggleType(type: BotType) {
    const set = new SvelteSet(activeTypes);
    if (set.has(type)) set.delete(type);
    else set.add(type);
    // Preserve the BOT_TYPES catalogue order so the chip order stays
    // stable across toggles (matches the catalogue display order).
    const next = BOT_TYPES.map((b) => b.value).filter((v) => set.has(v));
    ontypesChange?.(next);
  }

  function clearAll() {
    ontypesChange?.([]);
  }
</script>

<div class="bots-toolbar flex flex-wrap items-center gap-3" data-testid="bots-toolbar">
  <!-- Sort -->
  <div class="bots-toolbar-section flex items-center gap-2">
    <span class="bots-toolbar-label text-xs text-rp-text-secondary">
      {t('bot_library.sort_label', $lang)}
    </span>
    <Select
      options={SORT_OPTIONS}
      bind:value={sortValue}
      onchange={() => handleSortChange()}
    />
  </div>

  <!-- Type filter -->
  <div class="bots-toolbar-section flex items-center gap-2">
    <span class="bots-toolbar-label text-xs text-rp-text-secondary">
      {t('bot_library.filter_types_label', $lang)}
    </span>
    {#each BOT_TYPES as bt (bt.value)}
      {@const isActive = activeTypes.includes(bt.value)}
      <button
        type="button"
        class="bots-toolbar-chip min-h-11 inline-flex items-center gap-1 rounded-full border px-3 text-xs transition-opacity hover:opacity-80"
        class:chips-active={isActive}
        aria-pressed={isActive}
        onclick={() => toggleType(bt.value)}
      >
        <span aria-hidden="true">{bt.icon}</span>
        <span>{bt.label}</span>
        {#if isActive}
          <Badge variant="accent" size="sm">✓</Badge>
        {/if}
      </button>
    {/each}
    {#if activeTypes.length > 0}
      <button
        type="button"
        class="bots-toolbar-clear min-h-11 rounded-full px-3 text-xs text-rp-text-secondary underline-offset-2 hover:underline"
        onclick={clearAll}
      >
        {t('bot_library.filter_clear_all', $lang)}
      </button>
    {/if}
  </div>

  <!-- Search -->
  <div class="bots-toolbar-section flex-1 min-w-[12rem]">
    <Input
      type="search"
      value={query}
      placeholder={t('bot_library.search_placeholder', $lang)}
      oninput={(e: Event) => onqueryChange?.((e.target as HTMLInputElement).value)}
    />
  </div>
</div>

<style>
  /* Visual state for an active type chip — uses Raycast-style token,
     not a hardcoded hex. The contrast here is intentionally lower
     than button-pill-primary (DESIGN.md §Colors — "WCAG-AA exceptions"
     for chips/badges that are deliberately understated). */
  .chips-active {
    background-color: var(--ray-accent);
    color: var(--ray-text);
    border-color: var(--ray-accent);
  }

  /* Keep the clear-all button visually subtle — it should not
     compete with the active chips for attention. */
  .bots-toolbar-clear {
    background: transparent;
    border: none;
    cursor: pointer;
  }
</style>