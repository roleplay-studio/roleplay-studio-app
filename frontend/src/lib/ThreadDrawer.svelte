<script lang="ts">
  import type { Thread } from './api';

  import { api } from './api';
  import { t } from './i18n';
  import { formatRelativeTime } from './time';
  import { Select, ThreadItem } from './ui';
  import { sortThreads, THREAD_SORT_MODE_KEYS, type ThreadSortMode } from './utils/threadSort';

  const {
    lang = 'en',
    onclose,
    ondelete,
    onnew,
    onrename,
    onselect,
    selectedThreadId = null as null | number,
    threads = [] as Thread[],
  }: {
    botName?: string;
    lang?: string;
    onclose?: () => void;
    ondelete?: (id: number) => void;
    onnew?: () => void;
    onrename?: (id: number, name: string) => void;
    onselect?: (id: number) => void;
    selectedThreadId?: null | number;
    threads?: Thread[];
  } = $props();

  // ── Context menu state ──
  let contextThreadId = $state<null | number>(null);
  let contextX = $state(0);
  let contextY = $state(0);
  let showContextMenu = $state(false);
  let menuEl = $state<HTMLElement | null>(null);

  // ── Sort state — user-selectable mode. Default 'by-last-activity'
  // matches the backend's default ordering, so flipping through sorts
  // is reversible without the user losing their place. ──
  let sortMode = $state<ThreadSortMode>('by-last-activity');

  // Sorted view of the parent's ``threads`` — pure helper, no in-place
  // mutation of the input array so the parent's reactive update path
  // doesn't get confused.
  const sortedThreads = $derived(sortThreads(threads, sortMode));

  $effect(() => {
    if (!showContextMenu || !menuEl) return;
    requestAnimationFrame(() => {
      if (!menuEl) return;
      const rect = menuEl.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let x = contextX;
      let y = contextY;
      if (rect.right > vw) x = vw - rect.width - 12;
      if (rect.bottom > vh) y = vh - rect.height - 12;
      if (x < 8) x = 8;
      if (y < 8) y = 8;
      menuEl.style.left = `${x}px`;
      menuEl.style.top = `${y}px`;
    });
  });

  // ── Inline rename state ──
  let renamingThreadId = $state<null | number>(null);
  let renameValue = $state('');

  // ── Delete confirm state ──
  let deletingThreadId = $state<null | number>(null);

  function handleContextMenu(e: MouseEvent, threadId: number) {
    e.preventDefault();
    e.stopPropagation();
    contextThreadId = threadId;
    contextX = e.clientX;
    contextY = e.clientY;
    showContextMenu = true;
  }

  function closeContextMenu() {
    showContextMenu = false;
    contextThreadId = null;
  }

  function handleRenameClick() {
    if (contextThreadId === null) return;
    const thread = threads.find((t) => t.id === contextThreadId);
    if (!thread) return;
    renamingThreadId = contextThreadId;
    renameValue = thread.name;
    showContextMenu = false;
    setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>('.ti-rename-input');
      input?.focus();
      input?.select();
    }, 0);
  }

  async function commitRename() {
    if (renamingThreadId === null || !renameValue.trim()) {
      renamingThreadId = null;
      return;
    }
    try {
      await api.renameThread(renamingThreadId, renameValue.trim());
      onrename?.(renamingThreadId, renameValue.trim());
    } catch (e) {
      console.error('Failed to rename thread:', e);
    }
    renamingThreadId = null;
  }

  // ThreadItem calls onrename(id, name) — same shape as the existing
  // commit logic. Set the renaming id from the parameter, then commit.
  function commitRenameFromItem(id: number, name: string) {
    if (renamingThreadId !== id) {
      renamingThreadId = id;
    }
    renameValue = name;
    void commitRename();
  }

  function cancelRenameFromItem(_id: number) {
    renamingThreadId = null;
  }

  function handleDeleteClick() {
    if (contextThreadId === null) return;
    deletingThreadId = contextThreadId;
    showContextMenu = false;
  }

  async function confirmDelete() {
    if (deletingThreadId === null) return;
    try {
      await api.deleteThread(deletingThreadId);
      ondelete?.(deletingThreadId);
    } catch (e) {
      console.error('Failed to delete thread:', e);
    }
    deletingThreadId = null;
  }

  function cancelDelete() {
    deletingThreadId = null;
  }

  function selectThread(threadId: number) {
    if (renamingThreadId === threadId) return;
    onselect?.(threadId);
    onclose?.();
  }

  function handleGlobalClick() {
    if (showContextMenu) closeContextMenu();
  }
</script>

<svelte:window onclick={handleGlobalClick} />

<!-- Context menu -->
{#if showContextMenu}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="td-overlay" oncontextmenu={(e) => e.preventDefault()} onclick={closeContextMenu}>
    <div
      bind:this={menuEl}
      class="td-menu"
      style="left: {contextX}px; top: {contextY}px;"
      oncontextmenu={(e) => e.preventDefault()}
      onclick={(e) => e.stopPropagation()}
    >
      <button class="td-menu-item" onclick={handleRenameClick}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path><path
            d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
          ></path></svg
        >
        {t('thread.rename', lang)}
      </button>
      <div class="td-menu-divider"></div>
      <button class="td-menu-item danger" onclick={handleDeleteClick}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><polyline points="3 6 5 6 21 6"></polyline><path
            d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
          ></path></svg
        >
        {t('thread.delete', lang)}
      </button>
    </div>
  </div>
{/if}

<!-- Delete confirmation -->
{#if deletingThreadId !== null}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="td-del-overlay" onclick={cancelDelete}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div class="td-del-modal" onclick={(e) => e.stopPropagation()}>
      <div class="td-del-icon">
        <svg
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
      <h3 class="td-del-title">{t('thread.delete_confirm_title', lang)}</h3>
      <p class="td-del-msg">{t('thread.delete_confirm_msg', lang)}</p>
      <div class="td-del-actions">
        <button class="td-del-btn" onclick={cancelDelete}>{t('thread.cancel', lang)}</button>
        <button class="td-del-btn danger" onclick={confirmDelete}
          >{t('thread.delete_action', lang)}</button
        >
      </div>
    </div>
  </div>
{/if}

<div class="td-backdrop" onclick={onclose}></div>
<aside class="td-aside">
  <div class="td-header">
    <h2 class="td-title">{t('thread.title', lang)}</h2>
    <div class="td-header-actions">
      <button class="td-header-btn" onclick={onnew} title={t('thread.new', lang)}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"
          ></line></svg
        >
      </button>
      <button class="td-header-btn lg-hide" onclick={onclose} title={t('thread.close', lang)}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"
          ></line></svg
        >
      </button>
    </div>
  </div>

  <div class="td-list">
    {#each sortedThreads as thread (thread.id)}
      <ThreadItem
        {thread}
        lang={lang}
        timeLabel={formatRelativeTime(thread.created_at, lang)}
        selected={selectedThreadId === thread.id}
        renaming={renamingThreadId === thread.id}
        bind:renameValue
        onselect={selectThread}
        oncontextmenu={handleContextMenu}
        ondotsclick={handleContextMenu}
        onrename={commitRenameFromItem}
        oncancelrename={cancelRenameFromItem}
      />
    {/each}
  </div>
</aside>

<style>
  :root {
    --td-bg: #ffffff;
    --td-border: rgba(0, 0, 0, 0.06);
    --td-text: #1d1d1f;
    --td-text-secondary: #6e6e73;
    --td-text-tertiary: #86868b;
    --td-hover: rgba(0, 0, 0, 0.03);
    --td-selected: rgba(99, 102, 241, 0.08);
    --td-red: #ff3b30;
  }
  :root.dark {
    --td-bg: #101111;
    --td-border: rgba(255, 255, 255, 0.06);
    --td-text: #f9f9f9;
    --td-text-secondary: #9c9c9d;
    --td-text-tertiary: #6a6b6c;
    --td-hover: rgba(255, 255, 255, 0.03);
    --td-selected: rgba(99, 102, 241, 0.15);
    --td-red: #ff6363;
  }

  .td-overlay {
    position: fixed;
    inset: 0;
    z-index: 60;
  }
  .td-menu {
    position: fixed;
    z-index: 61;
    min-width: 140px;
    background: var(--td-bg);
    border: 1px solid var(--td-border);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    padding: 4px;
    overflow: hidden;
  }
  .td-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 10px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--td-text-secondary);
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.1s ease;
    text-align: left;
  }
  .td-menu-item:hover {
    background: var(--td-hover);
    color: var(--td-text);
  }
  .td-menu-item.danger:hover {
    background: color-mix(in srgb, var(--td-red) 10%, transparent);
    color: var(--td-red);
  }
  .td-menu-divider {
    height: 1px;
    margin: 2px 8px;
    background: var(--td-border);
  }

  .td-del-overlay {
    position: fixed;
    inset: 0;
    z-index: 70;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .td-del-modal {
    background: var(--td-bg);
    border: 1px solid var(--td-border);
    border-radius: 14px;
    padding: 24px;
    max-width: 340px;
    width: calc(100% - 32px);
    text-align: center;
  }
  .td-del-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--td-red) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
    color: var(--td-red);
  }
  .td-del-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--td-text);
    margin: 0 0 6px;
  }
  .td-del-msg {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    color: var(--td-text-secondary);
    margin: 0 0 20px;
    line-height: 1.5;
  }
  .td-del-actions {
    display: flex;
    gap: 8px;
  }
  .td-del-btn {
    flex: 1;
    padding: 9px 16px;
    border-radius: 86px;
    border: 1px solid var(--td-border);
    background: transparent;
    color: var(--td-text);
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.12s ease;
  }
  .td-del-btn:hover {
    opacity: 0.7;
  }
  .td-del-btn.danger {
    background: color-mix(in srgb, var(--td-red) 12%, transparent);
    border-color: color-mix(in srgb, var(--td-red) 20%, transparent);
    color: var(--td-red);
  }

  .td-backdrop {
    position: fixed;
    inset: 0;
    z-index: 30;
    background: rgba(0, 0, 0, 0.25);
  }
  :global(.dark) .td-backdrop {
    background: rgba(0, 0, 0, 0.45);
  }

  .td-aside {
    position: fixed;
    right: 0;
    top: 0;
    z-index: 40;
    width: 280px;
    height: 100vh;
    background: var(--td-bg);
    border-left: 1px solid var(--td-border);
    display: flex;
    flex-direction: column;
  }
  @media (min-width: 1024px) {
    .td-backdrop {
      background: transparent;
      pointer-events: none;
    }
    .td-aside {
      position: static;
      width: 260px;
      box-shadow: none;
    }
  }

  .td-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--td-border);
    flex-shrink: 0;
  }
  /* Sort bar — sits between header and list. Compact because the
     drawer is only 280px wide; the Select component handles its own
     chevron styling. */
  .td-sort {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--td-border);
    flex-shrink: 0;
  }
  .td-sort-label {
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    color: var(--td-text-tertiary, #86868b);
    letter-spacing: 0.2px;
  }
  .td-sort :global(.ray-select-container) {
    flex: 1;
  }
  .td-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--td-text);
    letter-spacing: 0.2px;
    margin: 0;
  }
  .td-header-actions {
    display: flex;
    gap: 4px;
  }
  .td-header-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--td-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .td-header-btn:hover {
    background: var(--td-hover);
    color: var(--td-text);
  }
  .lg-hide {
    display: flex;
  }
  @media (min-width: 1024px) {
    .lg-hide {
      display: none;
    }
  }

  .td-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
</style>
