<script lang="ts">
  import { onMount } from 'svelte';

  import type { RecentThread } from './api';

  import { thumbUrl } from './api';
  import { currentLang, t } from './i18n';
  import { GeneratedAvatar, Select, ThreadGroup } from './ui';
  import {
    groupThreadsByBot,
    THREAD_SORT_MODE_KEYS,
    type ThreadSortMode,
  } from './utils/threadSort';

  let lang = $state('en');

  const {
    loading = false,
    ondeleteThread,
    onselectThread,
    threads = [] as RecentThread[],
  }: {
    loading?: boolean;
    ondeleteThread?: (threadId: number) => void;
    onselectThread?: (botId: number, threadId: number) => void;
    threads?: RecentThread[];
  } = $props();

  // ── Sort state — mirrors ThreadDrawer's dropdown. Re-using the
  // same ThreadSortMode keeps a consistent UX across both surfaces
  // (per-bot drawer and cross-bot recent list). ──
  let sortMode = $state<ThreadSortMode>('by-last-activity');

  // ── Group-collapse state ───────────────────────────────────────
  // The user can collapse groups they're not actively reading. The
  // Set of collapsed bot_ids is persisted across sessions via
  // localStorage so the same muscle-memory layout is restored when
  // they come back. Hydration happens once onMount, with try/catch
  // around the JSON parse (legacy / corrupted entries silently
  // fall back to "all expanded").
  const COLLAPSE_STORAGE_KEY = 'rc_collapsed_bots';
  // Svelte 5 + ``svelteSet`` bug: wrapping a SvelteSet in ``$state``
  // does not propagate template subscriptions through the set's
  // mutation events (``SvelteSet`` is internally a separate signal
  // graph that ignores the wrapping rune). The collapsible-state
  // template ``{#if !isCollapsed && children}`` and
  // ``isCollapsed={collapsedBots.has(bot_id)}`` render only the
  // first group correctly when ``localStorage`` is empty, then fail
  // to react to ``.add()`` / ``.delete()`` calls.
  //
  // Fix: use a plain ``Set<number>`` inside a plain ``$state``.
  // ``$state`` makes ``collapsedBots`` a tracked signal, and plain
  // ``Set`` references are stable across the binding's reads —
  // any reassignment to ``collapsedBots = new Set(...)`` triggers a
  // template re-render and re-evaluates all ``.has()`` lookups.
  // Cost is one extra allocation per toggle, which is fine for a
  // user-action-driven action.
  let collapsedBots: Set<number> = $state(new Set());

  function loadCollapsedFromStorage(): Set<number> {
    try {
      const raw = localStorage.getItem(COLLAPSE_STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return new Set();
      return new Set(arr.filter((x) => typeof x === 'number'));
    } catch {
      return new Set();
    }
  }

  function persistCollapsedBots(set: Set<number>): void {
    try {
      localStorage.setItem(COLLAPSE_STORAGE_KEY, JSON.stringify([...set]));
    } catch {
      /* swallow — quota / private-mode failures must not crash the page */
    }
  }

  function toggleCollapsed(botId: number): void {
    // ``Set`` is the most ergonomic container here; ``SvelteSet``
    // would also satisfy ``svelte/prefer-svelte-reactivity`` but
    // empirically doesn't propagate set mutations through template
    // bindings in our Svelte version (see: ``collapsedMap`` derived
    // workaround two blocks below). Plain ``Set`` reassigned via
    // ``collapsedBots = next`` IS what makes the template re-render.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const next = new Set(collapsedBots);
    if (next.has(botId)) next.delete(botId);
    else next.add(botId);
    collapsedBots = next;
    persistCollapsedBots(next);
  }

  // Grouped view: re-derives whenever either ``threads`` or
  // ``sortMode`` changes. Within-group order is determined by
  // sortMode; inter-group order is always by newest activity.
  const groups = $derived(groupThreadsByBot(threads, sortMode));

  // Lookup table for collapsed state — keyed by bot_id. Built as
  // a derived Map so template bindings stay reactive. We previously
  // inlined ``collapsedBots.has(...)`` in the template and it did
  // not re-render on toggle (Svelte 5 + plain Set signal quirk).
  // The Map form forces a fresh concrete value each time the
  // source changes, which the compiler tracks correctly.
  const collapsedMap = $derived(new Map([...collapsedBots].map((id) => [id, true])));

  onMount(() => {
    currentLang.subscribe((v) => (lang = v));
    collapsedBots = loadCollapsedFromStorage();
  });

  let deletingId: null | number = $state(null);

  function formatTime(dateStr: null | string): string {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('chat.recent.just_now', lang);
    if (diffMin < 60) return t('chat.recent.min_ago', lang).replace('{n}', String(diffMin));
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return t('chat.recent.hr_ago', lang).replace('{n}', String(diffHrs));
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return t('chat.recent.day_ago', lang).replace('{n}', String(diffDays));
    return d.toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-US', {
      day: 'numeric',
      month: 'short',
    });
  }

  function truncate(text: string, max: number): string {
    if (text.length <= max) return text;
    return text.slice(0, max).trimEnd() + '…';
  }

  async function handleDelete(threadId: number) {
    if (deletingId !== null) return;
    deletingId = threadId;
    try {
      await ondeleteThread?.(threadId);
    } finally {
      deletingId = null;
    }
  }
</script>

<div class="rc-wrap">
  {#if loading}
    <div class="rc-loading">{t('chat.loading_recent', lang)}</div>
  {:else if threads.length === 0}
    <div class="rc-empty">
      <svg
        class="rc-empty-icon"
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path></svg
      >
      <p class="rc-empty-title">{t('chat.recent.no_chats', lang)}</p>
      <p class="rc-empty-hint">{t('chat.recent.no_chats_hint', lang)}</p>
    </div>
  {:else}
    {#if threads.length > 1}
      <div class="rc-sort">
        <Select
          bind:value={sortMode}
          options={[
            { label: t(THREAD_SORT_MODE_KEYS['by-last-activity'], lang), value: 'by-last-activity' },
            { label: t(THREAD_SORT_MODE_KEYS['by-message-count'], lang), value: 'by-message-count' },
            { label: t(THREAD_SORT_MODE_KEYS['by-name'], lang), value: 'by-name' },
          ]}
        />
      </div>
    {/if}
    <div class="rc-groups">
      {#each groups as group (group.bot_id)}
        <ThreadGroup
          bot_avatar_path={thumbUrl(group.bot_avatar_path, 200)}
          bot_categories={group.bot_categories}
          bot_name={group.bot_name}
          isCollapsed={collapsedMap.has(group.bot_id)}
          lastActivityLabel={formatTime(group.lastActivityAt)}
          onToggle={() => toggleCollapsed(group.bot_id)}
          threadCount={group.threads.length}
        >
          {#each group.threads as thread (thread.thread_id)}
            <div class="rc-card">
              <div
                class="rc-main"
                onclick={() => onselectThread?.(thread.bot_id, thread.thread_id)}
                role="button"
                tabindex="0"
                onkeydown={(e) =>
                  e.key === 'Enter' && onselectThread?.(thread.bot_id, thread.thread_id)}
              >
                <!-- Bot avatar (smaller now that we have the
                     group-level avatar above) -->
                {#if thread.bot_avatar_path}
                  <img
                    src={thumbUrl(thread.bot_avatar_path, 50)}
                    alt={thread.bot_name}
                    class="rc-avatar"
                  />
                {:else}
                  <GeneratedAvatar name={thread.bot_name} size={32} />
                {/if}

                <!-- Content -->
                <div class="rc-content">
                  <div class="rc-top">
                    <span class="rc-name">{thread.persona_name ?? thread.bot_name}</span>
                    <span class="rc-time">{formatTime(thread.last_message_at)}</span>
                  </div>

                  <div class="rc-bottom">
                    <p class="rc-preview" class:rc-summary={!!thread.summary && !thread.last_message_short_content}>
                      {#if thread.last_message_short_content}
                        {truncate(thread.last_message_short_content, 100)}
                      {:else if thread.summary}
                        {truncate(thread.summary, 120)}
                      {:else if thread.last_message_preview}
                        {truncate(thread.last_message_preview, 100)}
                      {:else}
                        {t('chat.recent.no_messages', lang)}
                      {/if}
                    </p>
                    {#if thread.message_count > 0}
                      <span class="rc-count">{thread.message_count}</span>
                    {/if}
                    {#if thread.persona_name}
                      <div class="rc-persona">
                        {#if thread.persona_avatar_path}
                          <img
                            src={thumbUrl(thread.persona_avatar_path, 50)}
                            alt=""
                            class="rc-persona-avatar"
                          />
                        {:else}
                          <div class="rc-persona-placeholder">
                            {thread.persona_name.charAt(0).toUpperCase()}
                          </div>
                        {/if}
                        <span>{thread.persona_name}</span>
                      </div>
                    {/if}
                  </div>
                </div>
              </div>

              <!-- Delete button -->
              <button
                class="rc-del"
                onclick={() => handleDelete(thread.thread_id)}
                disabled={deletingId === thread.thread_id}
                title={t('chat.recent.delete_title', lang)}
              >
                {#if deletingId === thread.thread_id}
                  <span class="rc-spinner"></span>
                {:else}
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
                {/if}
              </button>
            </div>
          {/each}
        </ThreadGroup>
      {/each}
    </div>
  {/if}
</div>

<style>
  /* ─── Theme variables ─── */
  :root {
    --rc-bg-card: #ffffff;
    --rc-border: rgba(0, 0, 0, 0.06);
    --rc-border-subtle: rgba(0, 0, 0, 0.04);
    --rc-text: #1d1d1f;
    --rc-text-secondary: #6e6e73;
    --rc-text-tertiary: #86868b;
    --rc-hover: rgba(0, 0, 0, 0.03);
    --rc-red: #ff3b30;
    --rc-shadow: rgba(0, 0, 0, 0.04);
    --rc-shadow-inset: rgba(0, 0, 0, 0.02);
  }
  :root.dark {
    --rc-bg-card: #101111;
    --rc-border: rgba(255, 255, 255, 0.06);
    --rc-border-subtle: rgba(255, 255, 255, 0.04);
    --rc-text: #f9f9f9;
    --rc-text-secondary: #9c9c9d;
    --rc-text-tertiary: #6a6b6c;
    --rc-hover: rgba(255, 255, 255, 0.03);
    --rc-red: #ff6363;
    --rc-shadow: rgb(27, 28, 30);
    --rc-shadow-inset: rgb(7, 8, 10);
  }

  .rc-wrap {
    font-family: 'Maple Mono', system-ui, sans-serif;
  }

  /* ─── Loading / Empty ─── */
  .rc-loading {
    text-align: center;
    padding: 40px 0;
    color: var(--rc-text-secondary);
    font-size: 14px;
  }
  .rc-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 0;
    color: var(--rc-text-tertiary);
  }
  .rc-empty-icon {
    margin-bottom: 12px;
  }
  .rc-empty-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--rc-text-secondary);
    margin: 0 0 4px;
  }
  .rc-empty-hint {
    font-size: 12px;
    color: var(--rc-text-tertiary);
    margin: 0;
  }

  /* Sort dropdown row. RecentChats renders above the list when
     the user has multiple threads to scroll through. */
  .rc-sort {
    margin-bottom: 6px;
  }
  .rc-sort :global(.ray-select-container) {
    width: 100%;
  }

  /* Groups container — each ``<ThreadGroup>`` already carries its
     own background, padding, and a sticky header. We just stack
     them with a tiny gap so they don't fuse visually.

     ``position: relative`` here is what makes the children's
     ``position: sticky`` resolve to *this* list (not the page
     viewport or some ancestor scroll container). Each group's
     sticky header will then "stick" within the page-level scroll. */
  .rc-groups {
    display: flex;
    flex-direction: column;
    gap: 0;
    position: relative;
    padding-bottom: 32px;
    /* ``margin-top`` is applied to each ``<ThreadGroup>`` instead
       of ``gap`` here. Reason: ``gap`` would place equal space
       between each group, but sticky group headers need to
       *stack* when scrolled — each one pins to the top until the
       next group's header pushes it up. A bottom margin on the
       group itself preserves that visual spacing without breaking
       the sticky stacking. */
  }
  /* rc-list was the legacy flat-list wrapper. Kept as an alias for
     tests / external CSS that may still reference it. */
  .rc-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  /* ─── Card ─── */
  /* Inside a ``<ThreadGroup>``, the group header is sticky at the
     top of the scroll container; we keep each card's top edge
     clear of the sticky bar via a small top margin and a rounded
     border so the group reads as one cohesive "block". */
  .rc-card {
    display: flex;
    align-items: stretch;
    background: var(--rc-bg-card);
    border: 1px solid var(--rc-border);
    border-radius: 10px;
    overflow: hidden;
    transition: all 0.15s ease;
    margin: 4px 8px 4px 8px;
  }
  .rc-card:hover {
    border-color: var(--rc-text-tertiary);
  }
  .rc-main {
    flex: 1;
    display: flex;
    gap: 12px;
    padding: 12px 14px;
    cursor: pointer;
    align-items: center;
    min-width: 0;
    transition: background 0.12s ease;
  }
  .rc-main:hover {
    background: var(--rc-hover);
  }

  /* ─── Avatar ─── */
  /* Inside a group the row-level avatar is intentionally smaller
     than the group-level avatar: the group header carries the
     "this is the bot" identity, the row avatar is just decoration. */
  .rc-avatar {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* ─── Content ─── */
  .rc-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .rc-top {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .rc-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--rc-text);
    letter-spacing: 0.2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rc-time {
    font-size: 10px;
    font-weight: 400;
    color: var(--rc-text-tertiary);
    margin-left: auto;
    white-space: nowrap;
    flex-shrink: 0;
    letter-spacing: 0.2px;
  }
  .rc-bottom {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rc-preview {
    font-size: 12px;
    font-weight: 400;
    color: var(--rc-text-secondary);
    letter-spacing: 0.15px;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }
  .rc-preview.rc-summary {
    color: var(--rc-text);
    font-style: italic;
  }
  .rc-persona {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    font-weight: 500;
    color: var(--rc-text-tertiary);
    white-space: nowrap;
    flex-shrink: 0;
    letter-spacing: 0.2px;
  }
  .rc-persona-avatar {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    object-fit: cover;
  }
  /* Message count pill — small numeric badge inline with the preview row.
     Numeric font-feature variant keeps digits monospace so the row
     doesn't jiggle as counts change. */
  .rc-count {
    flex-shrink: 0;
    font-size: 10px;
    font-weight: 600;
    color: var(--rc-text-secondary, #6e6e73);
    background: color-mix(in srgb, var(--rc-text, #1d1d1f) 6%, transparent);
    padding: 1px 6px;
    border-radius: 86px;
    font-feature-settings: 'tnum' 1;
    letter-spacing: 0.2px;
  }
  .rc-persona-placeholder {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: 600;
    color: #fff;
    background: linear-gradient(135deg, #8b5cf6, #06b6d4);
  }

  /* ─── Delete button ─── */
  .rc-del {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    border: none;
    border-left: 1px solid var(--rc-border);
    background: transparent;
    color: var(--rc-text-tertiary);
    cursor: pointer;
    transition: all 0.12s ease;
    flex-shrink: 0;
  }
  .rc-del:hover {
    background: color-mix(in srgb, var(--rc-red) 8%, transparent);
    color: var(--rc-red);
  }
  .rc-del:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .rc-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid color-mix(in srgb, var(--rc-red) 20%, transparent);
    border-top-color: var(--rc-red);
    border-radius: 50%;
    animation: rc-spin 0.6s linear infinite;
  }
  @keyframes rc-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
