<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, type Bot, type BotType } from '../api';
  import BotCard from '../BotCard.svelte';
  import {
    applyBotsFilters,
    type BotSortDir,
    type BotSortKey,
  } from '../botsBrowse';
  import BotsToolbar from '../BotsToolbar.svelte';
  import { currentLang, t } from '../i18n';
  import { Loading } from '../ui';
  import { isSupportedBotFile } from './bots-dnd';

  // Tauri runtime drag-drop fallback. HTML5 events (`dragenter`/`drop`)
  // work fine in a regular browser and on Tauri with dragDropEnabled=true,
  // but Tauri can also deliver absolute file paths via onDragDropEvent.
  // We use it as a safety net for the case where the HTML5 events are
  // blocked (e.g. some macOS WKWebView builds) so the import still works.
  let tauriUnlisten: (() => void) | undefined;
  async function setupTauriDragDrop() {
    // Only available inside a Tauri webview; import dynamically so the
    // regular browser build doesn't try to load it.
    if (typeof window === 'undefined') return;
    const w = window as unknown as {
      __TAURI_INTERNALS__?: unknown;
    };
    if (!w.__TAURI_INTERNALS__) return;

    try {
      const { getCurrentWebview } = await import('@tauri-apps/api/webview');
      const { readFile } = await import('@tauri-apps/plugin-fs');

      tauriUnlisten = await getCurrentWebview().onDragDropEvent(async (event) => {
        const t = event.payload.type;
        if (t === 'enter' || t === 'over') {
          isDragging = true;
          return;
        }
        if (t === 'leave') {
          isDragging = false;
          return;
        }
        if (t === 'drop') {
          isDragging = false;
          const path = event.payload.paths[0];
          if (!path) return;
          const name = path.split('/').pop() ?? '';
          if (!isSupportedBotFile(name)) {
            importError = t_msg('import.unsupported_file', lang);
            return;
          }
          try {
            const bytes = await readFile(path);
            const file = new File([bytes], name, {
              type: name.endsWith('.png')
                ? 'image/png'
                : name.endsWith('.json')
                  ? 'application/json'
                  : 'application/octet-stream',
            });
            await importBotFile(file);
          } catch (err) {
            console.error('Tauri drag-drop read failed:', err);
            importError = err instanceof Error ? err.message : String(err);
          }
        }
      });
    } catch (err) {
      // Plugin not available (dev web, etc.) — HTML5 handlers are enough.
      console.debug('Tauri drag-drop fallback unavailable:', err);
    }
  }

  // Local copy of t() to avoid shadowing the import; used inside the
  // async Tauri handler above.
  const t_msg = t;

  let lang = $state('en');
  let unsubLang: (() => void) | undefined;

  let bots: Bot[] = $state([]);
  let loading = $state(true);

  // Toolbar state (introduced by improve-bot-editor). Default sort is
  // ``id desc`` which is the chronological proxy for created_at
  // (created_at is NOT on BotResponse per design.md Q1). The toolbar
  // is a controlled component — these are the source of truth, and
  // BotsToolbar reads/writes them via callbacks.
  let sortKey: BotSortKey = $state('id');
  let sortDir: BotSortDir = $state('desc');
  let activeTypes: BotType[] = $state([]);
  let query: string = $state('');

  // Filtered + sorted view of the bot list. Pure derivation over the
  // raw ``bots`` + toolbar state via the botsBrowse helpers. The
  // template renders ``visibleBots`` instead of ``bots`` so the
  // toolbar's effects are visible immediately.
  let visibleBots: Bot[] = $derived(
    applyBotsFilters(bots, { query, sortDir, sortKey, types: activeTypes }),
  );

  onMount(() => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    loadBots();
    // Capture phase + stopImmediatePropagation lets us beat GlobalDropZone
    // (which is registered in the bubble phase at App mount).
    window.addEventListener('dragenter', onPageDragEnter, true);
    window.addEventListener('dragleave', onPageDragLeave, true);
    window.addEventListener('dragover', onPageDragOver, true);
    window.addEventListener('drop', onPageDrop, true);
    // Tauri-runtime fallback for environments where HTML5 events are blocked.
    void setupTauriDragDrop();
  });

  onDestroy(() => {
    unsubLang?.();
    window.removeEventListener('dragenter', onPageDragEnter, true);
    window.removeEventListener('dragleave', onPageDragLeave, true);
    window.removeEventListener('dragover', onPageDragOver, true);
    window.removeEventListener('drop', onPageDrop, true);
    tauriUnlisten?.();
  });

  async function loadBots() {
    try {
      bots = await api.listBots();
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  let importFileInput: HTMLInputElement | undefined = $state();
  let importError = $state('');
  let botToDelete: Bot | null = $state(null);
  let showDeleteModal = $derived(botToDelete !== null);

  async function doExport(bot: Bot, format: 'json' | 'png' = 'json') {
    try {
      await api.exportBot(bot.id, bot.name, format);
    } catch (e) {
      console.error(e);
      importError = e instanceof Error ? e.message : t('bots.export_error', lang);
    }
  }

  async function importFromFile() {
    const file = importFileInput?.files?.[0];
    if (!file) return;
    await importBotFile(file);
  }

  async function importBotFile(file: File) {
    importError = '';
    try {
      const { id } = await api.importBot(file);
      // Same race-guard as the global drop zone — wait for the new
      // bot to be readable through the API before redirecting, so the
      // edit page doesn't mount against a row that hasn't been
      // committed yet.
      const deadline = Date.now() + 2000;
      while (Date.now() < deadline) {
        try {
          await api.getBot(id);
          break;
        } catch {
          await new Promise((r) => setTimeout(r, 100));
        }
      }
      await loadBots();
      window.location.hash = `/bots/${id}/edit`;
    } catch (e) {
      console.error(e);
      importError = e instanceof Error ? e.message : t('bots.import_error', lang);
    } finally {
      if (importFileInput) importFileInput.value = '';
    }
  }

  let isDragging = $state(false);
  let dragCounter = 0;

  function onPageDragEnter(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    e.stopImmediatePropagation();
    dragCounter++;
    isDragging = true;
  }

  function onPageDragLeave(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    e.stopImmediatePropagation();
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) isDragging = false;
  }

  function onPageDragOver(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }

  async function onPageDrop(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    isDragging = false;
    dragCounter = 0;

    const file = e.dataTransfer?.files?.[0];
    if (!file) return;

    if (!isSupportedBotFile(file.name)) {
      importError = t('import.unsupported_file', lang);
      return;
    }
    await importBotFile(file);
  }

  function confirmDelete(bot: Bot) {
    botToDelete = bot;
  }

  async function doDelete() {
    if (!botToDelete) return;
    const bot = botToDelete;
    botToDelete = null;
    try {
      await api.deleteBot(bot.id);
      bots = bots.filter((b) => b.id !== bot.id);
    } catch (e) {
      console.error(e);
    }
  }

  function cancelDelete() {
    botToDelete = null;
  }

  function openCreate() {
    window.location.hash = '/bots/create';
  }

  function chatWith(bot: Bot) {
    window.location.hash = `/bot/${bot.id}`;
  }

  function editBot(bot: Bot) {
    window.location.hash = `/bots/${bot.id}`;
  }
</script>

<div class="bots-page">
  <!-- Header -->
  <header class="bots-header">
    <div>
      <h1 class="bots-title">{t('bots.title', lang)}</h1>
      <p class="bots-subtitle">{t('bots.subtitle_create_manage', lang)}</p>
    </div>
    <div class="bots-actions">
      <input
        type="file"
        accept=".json,.png,.webp,.jpg,.jpeg"
        bind:this={importFileInput}
        onchange={importFromFile}
        class="hidden"
      />
      <button class="ray-btn" onclick={() => importFileInput?.click()}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><path d="M7 10l5 5 5-5"
          ></path><path d="M12 15V3"></path></svg
        >
        {t('bots.import', lang)}
      </button>
      <button class="ray-btn primary" onclick={openCreate}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"
          ></line></svg
        >
        {t('bots.new_bot', lang)}
      </button>
    </div>
  </header>

  {#if importError}
    <div class="bots-error">{importError}</div>
  {/if}

  <!-- Toolbar: sort / type-filter / name-search. The toolbar owns no
       state of its own; it forwards user input to the callbacks which
       update the ``$state`` defined above, and the ``visibleBots``
       derivation re-runs to refresh the grid. -->
  {#if !loading && bots.length > 0}
    <BotsToolbar
      activeTypes={activeTypes}
      onqueryChange={(q) => (query = q)}
      onsortChange={(k, d) => {
        sortKey = k;
        sortDir = d;
      }}
      ontypesChange={(t) => (activeTypes = t)}
      {query}
      {sortDir}
      {sortKey}
    />
    <div class="bots-results-count text-xs text-rp-text-secondary">
      {t('bot_library.results_count', lang, {
        count: visibleBots.length,
        total: bots.length,
      })}
    </div>
  {/if}

  {#if loading}
    <div class="loading-wrap">
      <Loading size="lg" />
    </div>
  {:else if bots.length === 0}
    <div class="bots-empty">
      <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1"
          d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <p class="empty-title">{t('bots.no_bots', lang)}</p>
      <p class="empty-hint">{t('bots.no_bots_hint', lang)}</p>
    </div>
  {:else if visibleBots.length === 0}
    <!-- Toolbar is visible above; here we explain the empty result
         caused by the active filter rather than the underlying empty
         library. Distinct from ``bots.length === 0`` because the
         actions differ (clear filters vs. create a new bot). -->
    <div class="bots-empty">
      <p class="empty-title">{t('bot_library.empty_state', lang)}</p>
    </div>
  {:else}
    <div class="bots-grid">
      {#each visibleBots as bot (bot.id)}
        <BotCard
          {bot}
          showActions
          onchat={chatWith}
          onedit={editBot}
          onexport={doExport}
          ondelete={confirmDelete}
        />
      {/each}
      <!-- Always-visible drop hint as the last grid cell. Sits next to the
           cards so users know they can drop a file anywhere on the page.
           Doesn't intercept clicks — the existing Import button + file
           picker still handles the click path. -->
      <button
        type="button"
        class="bots-drop-hint"
        onclick={() => importFileInput?.click()}
        aria-label={t('import.drop_here', lang) || 'Drop character card or click to import'}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <span class="bots-drop-hint-title">
          {t('import.drop_here', lang) || 'Drop character card to import'}
        </span>
        <span class="bots-drop-hint-hint">.png · .json · .webp · .jpg</span>
      </button>
    </div>
  {/if}

  <!-- Local drop zone — shows when a file is being dragged anywhere over
       the page. Sits above .bots-page (z-50) but below modals (z-100+). -->
  {#if isDragging}
    <div class="bots-dropzone" aria-hidden="true">
      <div class="bots-dropzone-card">
        <svg
          width="64"
          height="64"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="bots-dropzone-icon"
        >
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <p class="bots-dropzone-title">
          {t('import.drop_here', lang) || 'Drop character card to import'}
        </p>
        <p class="bots-dropzone-hint">.png · .json · .webp · .jpg</p>
      </div>
    </div>
  {/if}
</div>

<!-- Delete Modal -->
{#if showDeleteModal}
  <div class="ray-modal-overlay" onclick={cancelDelete} role="presentation"></div>
  <div class="ray-modal">
    <div class="ray-modal-header">
      <h3 class="ray-modal-title">
        {botToDelete ? t('bots.delete_confirm', lang).replace('{name}', botToDelete.name) : ''}
      </h3>
    </div>
    <div class="ray-modal-body">
      <div class="ray-modal-icon-wrap">
        <svg
          class="ray-modal-icon"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path
            d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          ></path><line x1="12" y1="9" x2="12" y2="13"></line><line
            x1="12"
            y1="17"
            x2="12.01"
            y2="17"
          ></line></svg
        >
      </div>
      <p class="ray-modal-msg">{t('bots.delete_confirm_msg', lang)}</p>
    </div>
    <div class="ray-modal-footer">
      <button class="ray-btn" onclick={cancelDelete}>{t('common.cancel', lang)}</button>
      <button class="ray-btn danger" onclick={doDelete}>{t('common.delete', lang)}</button>
    </div>
  </div>
{/if}

<style>
  /* ─── Theme Variables ─── */
  :root {
    --ray-bg: #f5f5f7;
    --ray-bg-card: #ffffff;
    --ray-border: rgba(0, 0, 0, 0.06);
    --ray-border-strong: rgba(0, 0, 0, 0.1);
    --ray-border-subtle: rgba(0, 0, 0, 0.04);
    --ray-text: #1d1d1f;
    --ray-text-secondary: #6e6e73;
    --ray-text-tertiary: #86868b;
    --ray-red: #ff3b30;
    --ray-green: #34c759;
    --ray-blue: hsl(211, 100%, 50%);
    --ray-shadow-ring: rgba(0, 0, 0, 0.04);
    --ray-shadow-inset: rgba(0, 0, 0, 0.02);
    --ray-surface-raised: #f0f0f2;
    --ray-overlay: #ffffff;
    --ray-overlay-backdrop: rgba(0, 0, 0, 0.3);
  }
  :root.dark {
    --ray-bg: #07080a;
    --ray-bg-card: #101111;
    --ray-border: rgba(255, 255, 255, 0.06);
    --ray-border-strong: rgba(255, 255, 255, 0.1);
    --ray-border-subtle: rgba(255, 255, 255, 0.04);
    --ray-text: #f9f9f9;
    --ray-text-secondary: #9c9c9d;
    --ray-text-tertiary: #6a6b6c;
    --ray-red: #ff6363;
    --ray-green: #5fc992;
    --ray-blue: hsl(202, 100%, 67%);
    --ray-shadow-ring: rgb(27, 28, 30);
    --ray-shadow-inset: rgb(7, 8, 10);
    --ray-surface-raised: #1b1c1e;
    --ray-overlay: #1b1c1e;
    --ray-overlay-backdrop: rgba(0, 0, 0, 0.6);
  }

  .bots-page {
    padding: 32px 48px;
    color: var(--ray-text);
  }

  /* ─── Local drop zone ─── */
  .bots-dropzone {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--ray-text) 35%, transparent);
    backdrop-blur: 4px;
    pointer-events: none;
    animation: bots-dropzone-fade 0.15s ease-out;
  }
  .bots-dropzone-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 36px 56px;
    background: var(--ray-bg-card);
    border: 2px dashed var(--ray-blue);
    border-radius: 16px;
    box-shadow: 0 12px 40px color-mix(in srgb, #000 25%, transparent);
  }
  .bots-dropzone-icon {
    color: var(--ray-blue);
  }
  .bots-dropzone-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 18px;
    font-weight: 500;
    color: var(--ray-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .bots-dropzone-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text-tertiary);
    margin: 0;
    letter-spacing: 0.3px;
  }
  @keyframes bots-dropzone-fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  /* ─── Loading ─── */
  .loading-wrap {
    display: flex;
    justify-content: center;
    padding: 80px 0;
  }

  /* ─── Header ─── */
  .bots-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 32px;
    gap: 16px;
    flex-wrap: wrap;
  }
  .bots-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 28px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--ray-text);
  }
  .bots-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary);
    margin: 4px 0 0;
  }
  .bots-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  /* ─── Error ─── */
  .bots-error {
    margin-bottom: 16px;
    padding: 10px 14px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--ray-red) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--ray-red) 15%, transparent);
    color: var(--ray-red);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    letter-spacing: 0.2px;
  }

  /* ─── Empty state ─── */
  .bots-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    background: var(--ray-bg-card);
    border: 1px solid var(--ray-border);
    border-radius: 12px;
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      var(--ray-shadow-inset) 0px 0px 0px 1px inset;
  }
  .empty-icon {
    width: 48px;
    height: 48px;
    color: var(--ray-text-tertiary);
    margin-bottom: 16px;
  }
  .empty-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 16px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    margin-bottom: 4px;
  }
  .empty-hint {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    color: var(--ray-text-tertiary);
  }

  /* ─── Grid ─── */
  .bots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 12px;
  }

  /* ─── Results count (above the grid, below the toolbar) ─── */
  .bots-results-count {
    margin: 4px 0 12px;
  }

  /*
   * Mobile chip-row mask: per MOBILE_PLAN.md Phase 5, the filter chip
   * row in BotsToolbar scrolls horizontally on narrow viewports with
   * a fade mask that hints at overflow. The toolbar's chip section
   * already uses flex-wrap, but on <480px viewports the row is too
   * wide to wrap cleanly — overflow-x gives the scrollbar a place to
   * live. The mask lives on the wrapping section so the search input
   * below stays full-width.
   *
   * TODO(for-assistant): nth-of-type(2) is fragile — it relies on
   * BotsToolbar's section order being (sort, filter, search). If the
   * toolbar ever adds a 4th section before the filter chips, this
   * selector silently breaks. Replacement plan: add a stable class
   * like ``bots-toolbar-filter-section`` to the wrapping <div> in
   * BotsToolbar.svelte and target it directly here. Tracked for the
   * next refactor pass; no live bug.
   */
  @media (max-width: 767.98px) {
    :global(.bots-toolbar .bots-toolbar-section:nth-of-type(2)) {
      overflow-x: auto;
      scrollbar-width: none;
      mask-image: linear-gradient(
        to right,
        black 0,
        black calc(100% - 24px),
        transparent 100%
      );
    }
    :global(.bots-toolbar .bots-toolbar-section:nth-of-type(2)::-webkit-scrollbar) {
      display: none;
    }
  }

  /* ─── Drop hint (always-visible card-shaped placeholder) ─── */
  .bots-drop-hint {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 200px;
    padding: 24px;
    background: transparent;
    border: 2px dashed var(--ray-border-strong);
    border-radius: 14px;
    color: var(--ray-text-tertiary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .bots-drop-hint:hover {
    border-color: var(--ray-blue);
    color: var(--ray-blue);
    background: color-mix(in srgb, var(--ray-blue) 4%, transparent);
  }
  .bots-drop-hint-title {
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-align: center;
  }
  .bots-drop-hint-hint {
    font-size: 11px;
    letter-spacing: 0.3px;
    opacity: 0.7;
  }

  /* ─── Bot Card ─── */
  .bot-card {
    position: relative;
    background: var(--ray-bg-card);
    border: 1px solid var(--ray-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      var(--ray-shadow-inset) 0px 0px 0px 1px inset;
    transition: all 0.2s ease;
    cursor: default;
    display: flex;
    flex-direction: column;
  }
  .bot-card:hover {
    border-color: var(--ray-border-strong);
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      var(--ray-shadow-inset) 0px 0px 0px 1px inset,
      0 8px 28px color-mix(in srgb, #000 8%, transparent);
    transform: translateY(-1px);
  }

  /* ─── Hero image (full width) ─── */
  .card-hero {
    position: relative;
    width: 100%;
    height: 140px;
    overflow: hidden;
    background: color-mix(in srgb, var(--ray-text) 3%, transparent);
  }
  .card-hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }
  .bot-card:hover .card-hero-img {
    transform: scale(1.03);
  }
  .card-hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 56px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 2px;
  }
  .card-hero-glow {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60%;
    background: linear-gradient(to top, var(--ray-bg-card) 20%, transparent);
    pointer-events: none;
  }
  .card-hero-type {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: color-mix(in srgb, var(--ray-bg-card) 80%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    box-shadow: 0 2px 8px color-mix(in srgb, #000 20%, transparent);
  }
  .card-hero-threads {
    position: absolute;
    bottom: 10px;
    right: 10px;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 86px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    background: color-mix(in srgb, var(--ray-bg-card) 80%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.2px;
  }

  /* ─── Card Body ─── */
  .card-body {
    padding: 14px 18px 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1;
  }
  .card-name-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-name {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card-type-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 86px;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    background: color-mix(in srgb, var(--ray-text) 5%, transparent);
    color: var(--ray-text-secondary);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .card-type-label.rp {
    background: color-mix(in srgb, var(--ray-blue) 12%, transparent);
    color: var(--ray-blue);
  }
  .card-type-label.assistant {
    background: color-mix(in srgb, var(--ray-green) 12%, transparent);
    color: var(--ray-green);
  }
  .card-type-label.agent {
    background: color-mix(in srgb, #f59e0b 12%, transparent);
    color: #f59e0b;
  }

  .card-desc {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    letter-spacing: 0.15px;
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* ─── Meta row ─── */
  .card-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .card-cat {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 10px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    color: var(--ray-text-tertiary);
    letter-spacing: 0.3px;
  }

  /* ─── Actions overlay (appears on hover) ─── */
  .card-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 0 20px 12px 22px;
    opacity: 0;
    transform: translateY(4px);
    transition: all 0.2s ease;
    pointer-events: none;
  }
  .bot-card:hover .card-actions {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .card-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .card-action-btn:hover {
    background: color-mix(in srgb, var(--ray-text) 5%, transparent);
    color: var(--ray-text);
  }
  .card-action-btn.chat {
    color: var(--ray-blue);
  }
  .card-action-btn.chat:hover {
    background: color-mix(in srgb, var(--ray-blue) 10%, transparent);
  }
  .card-action-btn.danger {
    margin-left: auto;
  }
  .card-action-btn.danger:hover {
    background: color-mix(in srgb, var(--ray-red) 10%, transparent);
    color: var(--ray-red);
  }
  .card-actions-divider {
    width: 1px;
    height: 20px;
    background: var(--ray-border-subtle);
    margin: 0 4px;
  }

  /* ─── Modal ─── */
  .ray-modal-overlay {
    position: fixed;
    inset: 0;
    background: var(--ray-overlay-backdrop);
    z-index: 99;
  }
  .ray-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--ray-overlay);
    border: 1px solid var(--ray-border);
    border-radius: 14px;
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      0 16px 48px color-mix(in srgb, #000 20%, transparent);
    z-index: 100;
    width: 360px;
    max-width: 90vw;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .ray-modal-header {
    padding: 0;
  }
  .ray-modal-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: var(--ray-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .ray-modal-body {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .ray-modal-icon-wrap {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--ray-red) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .ray-modal-icon {
    color: var(--ray-red);
  }
  .ray-modal-msg {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
    line-height: 1.5;
    margin: 0;
  }
  .ray-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding-top: 4px;
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .bots-page {
      padding: 20px 16px;
    }
    .bots-header {
      flex-direction: column;
    }
    .bots-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
