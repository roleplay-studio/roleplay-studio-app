<script lang="ts">
  /**
   * VersionsTimeline — chronological list of bot versions.
   *
   * Parent owns the data + loading state. This component just renders
   * and emits user actions (view / restore / delete / save-new).
   */
  import { api, type Bot, type BotSnapshot, type BotVersion } from '../api';
  import { currentLang, t } from '../i18n';
  import Modal from './Modal.svelte';

  /**
   * Compute a longest-common-subsequence-based line diff between two
   * strings. Returns an array of { side: 'cur' | 'snap' | 'both', line }
   * suitable for side-by-side rendering. Lines unchanged on both sides
   * are returned as 'both' (collapsed by default in the UI).
   *
   * Uses the classic O(n*m) dynamic-programming table — fine for the
   * hundreds of lines we'd see in a bot's personality or scenario.
   */
  type DiffLine = { line: string; side: 'both' | 'cur' | 'snap' };

  function lineDiff(a: string, b: string): DiffLine[] {
    const aLines = a.split('\n');
    const bLines = b.split('\n');
    const n = aLines.length;
    const m = bLines.length;

    // Build LCS length table.
    const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        if (aLines[i] === bLines[j]) {
          dp[i][j] = dp[i + 1][j + 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
        }
      }
    }

    // Walk the table to produce an aligned list. We emit 'cur' / 'snap'
    // for lines unique to one side and 'both' for shared ones.
    const out: DiffLine[] = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (aLines[i] === bLines[j]) {
        out.push({ line: aLines[i], side: 'both' });
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) {
        out.push({ line: aLines[i], side: 'cur' });
        i++;
      } else {
        out.push({ line: bLines[j], side: 'snap' });
        j++;
      }
    }
    while (i < n) {
      out.push({ line: aLines[i++], side: 'cur' });
    }
    while (j < m) {
      out.push({ line: bLines[j++], side: 'snap' });
    }
    return out;
  }

  let {
    bot,
    botId,
    onAfterRestore,
  }: {
    /** Current bot state — passed to the diff modal so the user sees
     *  "now vs then" instead of an absolute snapshot. */
    bot: Bot;
    botId: number;
    /** Called after a successful restore so the parent can re-fetch the
     *  bot and refresh other tabs. */
    onAfterRestore?: () => Promise<void> | void;
  } = $props();

  let lang = $derived($currentLang);

  let versions = $state<BotVersion[]>([]);
  let loading = $state(true);
  let error = $state<null | string>(null);

  let saveOpen = $state(false);
  let saveNote = $state('');
  let saving = $state(false);

  let diffOpen = $state(false);
  let diffSnapshot = $state<BotSnapshot | null>(null);
  let diffVersionNumber = $state(0);
  let diffLoading = $state(false);
  /** When false, only lines that differ are shown. When true, the
   *  full current / snapshot text is rendered for context. Toggled by
   *  the "Show all" button in the diff modal. */
  let diffShowAll = $state(false);
  /** DOM refs for the scrollable diff columns, keyed by
   *  `<field>__cur` / `<field>__snap`. Populated on render; read by
   *  ``syncScroll`` to mirror one column onto the other. */
  let colEls = $state<Record<string, HTMLElement | null>>({});
  /** Anti-feedback latch. When we programmatically scroll a column
   *  to mirror the user's scroll, the ``onscroll`` handler on that
   *  column would re-fire and bounce back. We tag the source so the
   *  receiver can ignore its own outgoing event. */
  let suppressScrollField: null | string = null;

  function syncScroll(field: string, side: 'cur' | 'snap', source: HTMLElement) {
    if (suppressScrollField === field) {
      // This scroll event was caused by us mirroring — skip.
      return;
    }
    const targetKey = `${field}__${side === 'cur' ? 'snap' : 'cur'}`;
    const target = colEls[targetKey];
    if (!target) return;
    suppressScrollField = field;
    try {
      // ``scrollTop`` is enough for line-by-line diffs; using
      // ``scrollTo`` keeps the receiver pinned while we mirror.
      target.scrollTop = source.scrollTop;
    } finally {
      // Defer clearing the latch until after the receiver's scroll
      // event has been processed.
      requestAnimationFrame(() => {
        suppressScrollField = null;
      });
    }
  }

  let confirmRestoreId = $state<null | number>(null);
  let confirmDeleteId = $state<null | number>(null);
  let acting = $state(false);
  let restoreModalOpen = $derived(confirmRestoreId !== null);
  let deleteModalOpen = $derived(confirmDeleteId !== null);
  function closeRestoreModal() {
    confirmRestoreId = null;
  }
  function closeDeleteModal() {
    confirmDeleteId = null;
  }

  async function reload() {
    loading = true;
    error = null;
    try {
      versions = await api.listBotVersions(botId);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (botId) void reload();
  });

  // When the diff modal opens or the user toggles "show full content",
  // reset both columns to the top so the user starts reading from the
  // first change instead of wherever they left off last time.
  $effect(() => {
    // Track diffSnapshot and diffShowAll so this re-runs on either change.
    void diffSnapshot;
    void diffShowAll;
    requestAnimationFrame(() => {
      for (const el of Object.values(colEls)) {
        if (el) el.scrollTop = 0;
      }
    });
  });

  async function handleSave() {
    saving = true;
    try {
      await api.createBotVersion(botId, saveNote.trim());
      saveNote = '';
      saveOpen = false;
      await reload();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  async function openDiff(versionId: number) {
    diffOpen = true;
    diffLoading = true;
    diffSnapshot = null;
    diffShowAll = false;
    try {
      const full = await api.getBotVersion(botId, versionId);
      diffSnapshot = full.snapshot;
      diffVersionNumber = full.version_number;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      diffLoading = false;
    }
  }

  async function handleRestore() {
    if (confirmRestoreId === null) return;
    acting = true;
    try {
      await api.restoreBotVersion(botId, confirmRestoreId);
      confirmRestoreId = null;
      await reload();
      await onAfterRestore?.();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      acting = false;
    }
  }

  async function handleDelete() {
    if (confirmDeleteId === null) return;
    acting = true;
    try {
      await api.deleteBotVersion(botId, confirmDeleteId);
      confirmDeleteId = null;
      await reload();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      acting = false;
    }
  }

  function fmtDate(iso: string): string {
    try {
      const d = new Date(iso);
      return d.toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-US', {
        dateStyle: 'short',
        timeStyle: 'short',
      });
    } catch {
      return iso;
    }
  }
</script>

<div class="vt-wrap">
  <div class="vt-header">
    <button class="ray-btn primary" onclick={() => (saveOpen = true)}>
      + {t('bot_versions.save', lang)}
    </button>
  </div>

  {#if error}
    <div class="vt-error">{error}</div>
  {/if}

  {#if loading}
    <div class="vt-empty">{t('app.loading', lang)}</div>
  {:else if versions.length === 0}
    <div class="vt-empty">{t('bot_versions.empty', lang)}</div>
  {:else}
    <ol class="vt-list">
      {#each versions as v (v.id)}
        <li class="vt-item" class:vt-auto={v.source === 'auto'}>
          <div class="vt-dot"></div>
          <div class="vt-body">
            <div class="vt-line">
              <span class="vt-num">#{v.version_number}</span>
              <span class="vt-date">{fmtDate(v.created_at)}</span>
              <span
                class="vt-badge"
                class:vt-badge-auto={v.source === 'auto'}
                class:vt-badge-manual={v.source === 'manual'}
              >
                {v.source === 'auto'
                  ? t('bot_versions.badge.auto', lang)
                  : t('bot_versions.badge.manual', lang)}
              </span>
            </div>
            {#if v.note}
              <p class="vt-note">{v.note}</p>
            {/if}
            <div class="vt-actions">
              <button class="ray-btn small" onclick={() => openDiff(v.id)}>
                {t('bot_versions.view', lang)}
              </button>
              <button class="ray-btn small" onclick={() => (confirmRestoreId = v.id)}>
                {t('bot_versions.restore', lang)}
              </button>
              <button class="ray-btn small danger" onclick={() => (confirmDeleteId = v.id)}>
                {t('bot_versions.delete', lang)}
              </button>
            </div>
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<!-- Save modal -->
<Modal
  bind:open={saveOpen}
  title={t('bot_versions.save', lang)}
  size="sm"
  onclose={() => (saveNote = '')}
>
  <label class="vt-label">
    {t('bot_versions.note.label', lang)}
    <textarea
      class="vt-textarea"
      bind:value={saveNote}
      placeholder={t('bot_versions.note.placeholder', lang)}
      rows="3"
    ></textarea>
  </label>
  {#snippet footer()}
    <button class="ray-btn" onclick={() => (saveOpen = false)}>
      {t('bot_edit.edit_cancel', lang)}
    </button>
    <button class="ray-btn primary" disabled={saving} onclick={handleSave}>
      {#if saving}<span class="btn-spinner"></span>{/if}
      {t('bot_versions.save', lang)}
    </button>
  {/snippet}
</Modal>

<!-- Diff modal — current vs snapshot, field by field -->
<Modal
  bind:open={diffOpen}
  title={t('bot_versions.diff.title', lang, { n: diffVersionNumber })}
  class="vt-diff-modal"
>
  {#if diffLoading}
    <div class="vt-empty">{t('app.loading', lang)}</div>
  {:else if diffSnapshot}
    {@const fields: Array<[string, string, string]> = [
      ['name', bot.name ?? '', diffSnapshot.name ?? ''],
      ['description', bot.description ?? '', diffSnapshot.description ?? ''],
      ['personality', bot.personality ?? '', diffSnapshot.personality ?? ''],
      [
        'first_message',
        bot.first_message ?? '',
        diffSnapshot.first_message ?? '',
      ],
      ['scenario', bot.scenario ?? '', diffSnapshot.scenario ?? ''],
      [
        'categories',
        (bot.categories ?? []).join(', '),
        (diffSnapshot.categories ?? []).join(', '),
      ],
      [
        'alternate_greetings',
        (bot.alternate_greetings ?? []).join('\n'),
        (diffSnapshot.alternate_greetings ?? []).join('\n'),
      ],
      [
        'mes_example',
        bot.mes_example ?? '',
        diffSnapshot.mes_example ?? '',
      ],
    ]}
    {@const changedFields = fields.filter(([, cur, snap]) => cur !== snap)}
    {#if changedFields.length === 0}
      <div class="vt-empty">{t('bot_versions.no_changes', lang)}</div>
    {:else}
      <div class="vt-diff-toolbar">
        <button class="ray-btn small" onclick={() => (diffShowAll = !diffShowAll)}>
          {diffShowAll ? t('bot_versions.show_changes', lang) : t('bot_versions.show_all', lang)}
        </button>
      </div>
      <div class="vt-diff-wrap">
        {#each changedFields as [field, cur, snap] (field)}
          {@const lines = lineDiff(cur, snap)}
          {@const visibleLines = diffShowAll ? lines : lines.filter((l) => l.side !== 'both')}
          <section class="vt-diff-field">
            <h4 class="vt-diff-field-name">{field}</h4>
            <div class="vt-diff-grid" data-diff-field={field}>
              <div class="vt-diff-col vt-diff-col-cur">
                <div class="vt-diff-col-head">
                  {t('bot_versions.diff.now', lang)}
                </div>
                <div
                  class="vt-diff-body"
                  bind:this={colEls[`${field}__cur`]}
                  onscroll={(e) => syncScroll(field, 'cur', e.currentTarget as HTMLElement)}
                >
                  <pre>{#each visibleLines as l, i (i)}{#if l.side === 'cur' || l.side === 'both'}<span
                          class="vt-line"
                          class:vt-line-cur={l.side === 'cur'}>{l.line || ' '}</span
                        >{:else}<span class="vt-line vt-line-empty"></span>{/if}
                    {/each}</pre>
                </div>
              </div>
              <div class="vt-diff-col vt-diff-col-snap">
                <div class="vt-diff-col-head">
                  v{diffVersionNumber}
                </div>
                <div
                  class="vt-diff-body"
                  bind:this={colEls[`${field}__snap`]}
                  onscroll={(e) => syncScroll(field, 'snap', e.currentTarget as HTMLElement)}
                >
                  <pre>{#each visibleLines as l, i (i)}{#if l.side === 'snap' || l.side === 'both'}<span
                          class="vt-line"
                          class:vt-line-snap={l.side === 'snap'}>{l.line || ' '}</span
                        >{:else}<span class="vt-line vt-line-empty"></span>{/if}
                    {/each}</pre>
                </div>
              </div>
            </div>
          </section>
        {/each}
      </div>
    {/if}
  {/if}
</Modal>

<!-- Confirm restore -->
<Modal
  bind:open={
    () => restoreModalOpen,
    (v) => {
      if (!v) closeRestoreModal();
    }
  }
  title={t('bot_versions.restore', lang)}
  size="sm"
  onclose={closeRestoreModal}
>
  <p>
    {t('bot_versions.confirm.restore', lang, {
      n: versions.find((v) => v.id === confirmRestoreId)?.version_number ?? '?',
    })}
  </p>
  {#snippet footer()}
    <button class="ray-btn" onclick={closeRestoreModal}>
      {t('bot_edit.edit_cancel', lang)}
    </button>
    <button class="ray-btn primary" disabled={acting} onclick={handleRestore}>
      {#if acting}<span class="btn-spinner"></span>{/if}
      {t('bot_versions.restore', lang)}
    </button>
  {/snippet}
</Modal>

<!-- Confirm delete -->
<Modal
  bind:open={
    () => deleteModalOpen,
    (v) => {
      if (!v) closeDeleteModal();
    }
  }
  title={t('bot_versions.delete', lang)}
  size="sm"
  onclose={closeDeleteModal}
>
  <p>
    {t('bot_versions.confirm.delete', lang, {
      n: versions.find((v) => v.id === confirmDeleteId)?.version_number ?? '?',
    })}
  </p>
  {#snippet footer()}
    <button class="ray-btn" onclick={closeDeleteModal}>
      {t('bot_edit.edit_cancel', lang)}
    </button>
    <button class="ray-btn danger" disabled={acting} onclick={handleDelete}>
      {#if acting}<span class="btn-spinner"></span>{/if}
      {t('bot_versions.delete', lang)}
    </button>
  {/snippet}
</Modal>

<style>
  .vt-wrap {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .vt-header {
    display: flex;
    justify-content: flex-end;
  }
  .vt-error {
    padding: 0.75rem 1rem;
    background: var(--ray-red-bg, rgba(255, 99, 99, 0.1));
    color: var(--ray-red, #ff5b5b);
    border-radius: 6px;
  }
  .vt-empty {
    padding: 2rem 1rem;
    text-align: center;
    color: var(--ray-text-muted, #888);
    font-size: 0.9rem;
  }
  .vt-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    position: relative;
  }
  .vt-item {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--ray-surface, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
  }
  .vt-dot {
    width: 10px;
    height: 10px;
    margin-top: 0.4rem;
    border-radius: 50%;
    background: var(--ray-accent, #6c8cff);
  }
  .vt-auto .vt-dot {
    background: var(--ray-text-muted, #888);
  }
  .vt-body {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .vt-line {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .vt-num {
    font-weight: 600;
    font-family: var(--ray-font-mono, monospace);
  }
  .vt-date {
    color: var(--ray-text-secondary, #aaa);
    font-size: 0.85rem;
  }
  .vt-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .vt-badge-auto {
    background: var(--ray-bg-soft, rgba(255, 255, 255, 0.06));
    color: var(--ray-text-secondary, #aaa);
  }
  .vt-badge-manual {
    background: var(--ray-accent-soft, rgba(108, 140, 255, 0.15));
    color: var(--ray-accent, #6c8cff);
  }
  .vt-note {
    margin: 0;
    font-size: 0.9rem;
    color: var(--ray-text-secondary, #ccc);
    font-style: italic;
  }
  .vt-actions {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.25rem;
  }
  .vt-label {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.85rem;
  }
  .vt-textarea {
    width: 100%;
    resize: vertical;
    padding: 0.5rem;
    border-radius: 6px;
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.1));
    background: var(--ray-surface-raised, rgba(255, 255, 255, 0.04));
    color: inherit;
    font-family: inherit;
  }
  .vt-diff-toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0.75rem;
  }
  /* Modal ignores the ``class`` prop in its API but renders the
   * ``_className`` string we splice into ``.rm-dialog``. 80vw gives
   * us enough room for the side-by-side diff columns to read long
   * lines without wrapping. Capped at 1400px so ultrawide monitors
   * don't get comically wide modals. ``!important`` overrides the
   * size preset (``.rm-md { max-width: 520px }``). */
  :global(.vt-diff-modal.rm-dialog) {
    max-width: min(80vw, 1400px) !important;
    width: min(80vw, 1400px);
  }
  .vt-diff-wrap {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }
  .vt-diff-field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .vt-diff-field-name {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ray-text-secondary, #aaa);
  }
  .vt-diff-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    overflow: hidden;
  }
  .vt-diff-col {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .vt-diff-col-cur {
    background: var(--ray-red-bg, rgba(255, 99, 99, 0.05));
  }
  .vt-diff-col-snap {
    background: var(--ray-accent-soft, rgba(108, 140, 255, 0.06));
  }
  .vt-diff-col-head {
    padding: 0.35rem 0.6rem;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ray-text-secondary, #aaa);
    border-bottom: 1px solid var(--ray-border, rgba(255, 255, 255, 0.06));
    background: var(--ray-surface-raised, rgba(255, 255, 255, 0.02));
  }
  .vt-diff-body {
    margin: 0;
    padding: 0.5rem 0.6rem;
    font-family: inherit;
    font-size: 0.85rem;
    line-height: 1.45;
    max-height: 22rem;
    overflow: auto;
  }
  .vt-diff-body pre {
    margin: 0;
    /* Preserve the snapshot's intentional newlines (one rendered
     * ``<span class="vt-line">`` per source line) but allow long
     * lines to wrap inside the modal instead of overflowing. */
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
  }
  .vt-line {
    display: block;
    padding: 0 0.25rem;
    border-radius: 2px;
  }
  .vt-line-cur {
    background: var(--ray-red-bg, rgba(255, 99, 99, 0.18));
    color: var(--ray-red, #ff8a8a);
    text-decoration: line-through;
    text-decoration-color: rgba(255, 138, 138, 0.5);
  }
  .vt-line-snap {
    background: var(--ray-accent-soft, rgba(108, 140, 255, 0.22));
    color: var(--ray-accent, #6c8cff);
  }
  .vt-line-empty {
    visibility: hidden;
  }
  .vt-diff {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  .vt-diff th,
  .vt-diff td {
    text-align: left;
    vertical-align: top;
    padding: 0.5rem;
    border-bottom: 1px solid var(--ray-border, rgba(255, 255, 255, 0.06));
  }
  .vt-diff th {
    width: 8rem;
    color: var(--ray-text-secondary, #aaa);
    font-weight: 500;
  }
  .vt-diff pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
  }
  .vt-diff tr.vt-changed {
    background: var(--ray-accent-soft, rgba(108, 140, 255, 0.08));
  }
  .btn-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-right: 4px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
