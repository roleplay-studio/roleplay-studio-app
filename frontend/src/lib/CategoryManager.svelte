<!--
  CategoryManager.svelte — manages the user-editable list of bot categories.

  Lives inside Settings. Reads from /api/bots/categories, lets the
  user add / rename / delete categories. Bots that reference
  now-removed categories keep them in their JSON column; the
  dashboard surfaces those via ``categories_invalid`` and this
  component does not need to know about that side.

  The list is order-preserving — we never sort alphabetically,
  because the dashboard filter dropdown reads the same order and the
  user expects "Anime, Game, Fantasy" to stay in the position they
  placed them.

  Visual:
  * Each row is a horizontal flex with: position number, name (or
    edit input), and right-aligned action buttons.
  * Icons are inline SVG (stroke-based, 1.6px, currentColor) — no
    emoji, no icon font. Hover/focus states inherit theme tokens.
-->
<script lang="ts">
  import { onMount } from 'svelte';

  import { api } from './api';
  import { currentLang, t } from './i18n';
  import { Loading } from './ui';

  let lang = $state('en');
  onMount(() => currentLang.subscribe((v) => (lang = v)));

  let categories = $state<string[]>([]);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state('');
  let draft = $state('');
  let editingIndex = $state<null | number>(null);
  let editValue = $state('');

  async function refresh() {
    loading = true;
    try {
      categories = await api.categories();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  async function add() {
    const name = draft.trim();
    if (!name) return;
    busy = true;
    error = '';
    try {
      categories = await api.addCategory(name);
      draft = '';
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  function startEdit(idx: number) {
    editingIndex = idx;
    editValue = categories[idx];
  }

  function cancelEdit() {
    editingIndex = null;
    editValue = '';
  }

  async function commitEdit(idx: number) {
    const oldName = categories[idx];
    const newName = editValue.trim();
    if (!newName || oldName === newName) {
      cancelEdit();
      return;
    }
    busy = true;
    error = '';
    try {
      categories = await api.renameCategory(oldName, newName);
      cancelEdit();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function remove(name: string) {
    if (!confirm(t('settings.categories.confirm_delete', lang, { name }))) {
      return;
    }
    busy = true;
    error = '';
    try {
      categories = await api.deleteCategory(name);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function onKey(e: KeyboardEvent) {
    if (e.key === 'Enter') await add();
  }

  async function onEditKey(e: KeyboardEvent, idx: number) {
    if (e.key === 'Enter') await commitEdit(idx);
    else if (e.key === 'Escape') cancelEdit();
  }
</script>

<section class="cm">
  <h3 class="cm-title">{t('settings.categories.title', lang)}</h3>
  <p class="cm-help">{t('settings.categories.help', lang)}</p>

  {#if loading}
    <Loading />
  {:else}
    <ol class="cm-list" aria-label={t('settings.categories.title', lang)}>
      {#each categories as cat, idx (cat)}
        <li class="cm-item" class:cm-item-editing={editingIndex === idx}>
          <span class="cm-pos" aria-hidden="true">{idx + 1}</span>

          {#if editingIndex === idx}
            <input
              class="cm-edit"
              bind:value={editValue}
              disabled={busy}
              onkeydown={(e) => onEditKey(e, idx)}
              autofocus
            />
            <div class="cm-actions">
              <button
                class="cm-iconbtn primary"
                disabled={busy}
                onclick={() => commitEdit(idx)}
                title={t('common.save', lang)}
                aria-label={t('common.save', lang)}
                type="button"
              >
                <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                  <path
                    d="M4 10.5l4 4 8-9"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
              <button
                class="cm-iconbtn"
                disabled={busy}
                onclick={cancelEdit}
                title={t('common.cancel', lang)}
                aria-label={t('common.cancel', lang)}
                type="button"
              >
                <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                  <path
                    d="M5 5l10 10M15 5L5 15"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
            </div>
          {:else}
            <span class="cm-name">{cat}</span>
            <div class="cm-actions">
              <button
                class="cm-iconbtn"
                disabled={busy}
                onclick={() => startEdit(idx)}
                title={t('settings.categories.rename', lang)}
                aria-label={t('settings.categories.rename', lang)}
                type="button"
              >
                <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                  <path
                    d="M3 17h3l9.5-9.5a1.5 1.5 0 0 0 0-2.12l-1.38-1.38a1.5 1.5 0 0 0-2.12 0L2.5 13.5V17z"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path
                    d="M11.5 5.5l3 3"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
              <button
                class="cm-iconbtn danger"
                disabled={busy}
                onclick={() => remove(cat)}
                title={t('settings.categories.delete', lang)}
                aria-label={t('settings.categories.delete', lang)}
                type="button"
              >
                <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                  <path
                    d="M5 5l10 10M15 5L5 15"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
            </div>
          {/if}
        </li>
      {/each}
    </ol>

    <div class="cm-add">
      <input
        class="cm-input"
        placeholder={t('settings.categories.placeholder', lang)}
        bind:value={draft}
        onkeydown={onKey}
        disabled={busy}
      />
      <button class="cm-btn primary" disabled={busy || !draft.trim()} onclick={add} type="button">
        <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
          <path
            d="M10 4v12M4 10h12"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
        <span>{t('settings.categories.add', lang)}</span>
      </button>
    </div>
  {/if}

  {#if error}
    <p class="cm-error" role="alert">{error}</p>
  {/if}
</section>

<style>
  .cm {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .cm-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
  .cm-help {
    margin: 0;
    color: var(--text-secondary, #6e6e73);
    font-size: 12px;
  }

  /* ── List ──────────────────────────────────────────── */
  .cm-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0;
    margin: 0;
    list-style: none;
  }
  .cm-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 6px;
    background: var(--bg-row, rgba(0, 0, 0, 0.025));
    border: 1px solid transparent;
    transition:
      background 0.12s ease,
      border-color 0.12s ease;
  }
  .cm-item:hover {
    background: var(--bg-row-hover, rgba(0, 0, 0, 0.05));
  }
  .cm-item-editing {
    border-color: var(--accent, hsl(211, 100%, 50%));
    background: var(--bg-row-active, rgba(0, 0, 0, 0.06));
  }
  :root.dark .cm-item-editing {
    border-color: hsl(202, 100%, 67%);
  }

  .cm-pos {
    flex: 0 0 auto;
    width: 20px;
    text-align: center;
    font-family: 'Maple Mono', ui-monospace, monospace;
    font-size: 11px;
    color: var(--text-secondary, #6e6e73);
    opacity: 0.7;
  }
  .cm-name {
    flex: 1 1 auto;
    min-width: 0;
    font-size: 13px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ── Inputs ────────────────────────────────────────── */
  .cm-edit,
  .cm-input {
    flex: 1 1 auto;
    min-width: 0;
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid var(--border, rgba(0, 0, 0, 0.1));
    background: var(--bg-input, #fff);
    color: inherit;
    font-size: 13px;
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .cm-edit:focus,
  .cm-input:focus {
    outline: none;
    border-color: var(--accent, hsl(211, 100%, 50%));
  }
  :root.dark .cm-edit,
  :root.dark .cm-input {
    background: hsl(220, 8%, 14%);
    border-color: rgba(255, 255, 255, 0.08);
  }

  /* ── Add row ───────────────────────────────────────── */
  .cm-add {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 4px;
  }
  .cm-input {
    margin: 0;
  }
  .cm-btn {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid transparent;
    cursor: pointer;
    font-size: 13px;
    font-family: inherit;
    transition:
      background 0.12s ease,
      opacity 0.12s ease;
  }
  .cm-btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  .cm-btn.primary {
    background: var(--accent, hsl(211, 100%, 50%));
    border-color: var(--accent, hsl(211, 100%, 50%));
    color: white;
  }
  .cm-btn.primary:hover:not(:disabled) {
    filter: brightness(0.95);
  }
  :root.dark .cm-btn.primary {
    background: hsl(202, 100%, 67%);
    border-color: hsl(202, 100%, 67%);
    color: #0b0b0e;
  }

  /* ── Icon buttons (edit/delete) ──────────────────── */
  .cm-actions {
    display: flex;
    gap: 2px;
    flex: 0 0 auto;
    margin-left: auto;
  }
  .cm-iconbtn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: 6px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary, #6e6e73);
    cursor: pointer;
    transition:
      background 0.12s ease,
      color 0.12s ease,
      border-color 0.12s ease;
  }
  .cm-iconbtn:hover:not(:disabled) {
    background: var(--bg-iconbtn-hover, rgba(0, 0, 0, 0.06));
    color: var(--text-primary, #1d1d1f);
  }
  .cm-iconbtn:disabled {
    cursor: not-allowed;
    opacity: 0.4;
  }
  .cm-iconbtn.primary {
    color: var(--accent, hsl(211, 100%, 50%));
  }
  .cm-iconbtn.primary:hover:not(:disabled) {
    background: color-mix(in srgb, var(--accent, hsl(211, 100%, 50%)) 12%, transparent);
  }
  :root.dark .cm-iconbtn.primary {
    color: hsl(202, 100%, 67%);
  }
  .cm-iconbtn.danger:hover:not(:disabled) {
    color: hsl(0, 70%, 55%);
    background: color-mix(in srgb, hsl(0, 70%, 55%) 10%, transparent);
  }

  /* ── Error ────────────────────────────────────────── */
  .cm-error {
    margin: 0;
    color: hsl(0, 70%, 50%);
    font-size: 12px;
  }
</style>
