<script lang="ts">
  import { onMount } from 'svelte';

  import type { RecentThread } from './api';

  import { thumbUrl } from './api';
  import { currentLang, t } from './i18n';
  import { GeneratedAvatar, Select } from './ui';
  import { sortRecentThreads, THREAD_SORT_MODE_KEYS, type ThreadSortMode } from './utils/threadSort';

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
  const sortedThreads = $derived(sortRecentThreads(threads, sortMode));

  onMount(() => currentLang.subscribe((v) => (lang = v)));

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
    <div class="rc-list">
      {#each sortedThreads as thread (thread.thread_id)}
        <div class="rc-card">
          <div
            class="rc-main"
            onclick={() => onselectThread?.(thread.bot_id, thread.thread_id)}
            role="button"
            tabindex="0"
            onkeydown={(e) =>
              e.key === 'Enter' && onselectThread?.(thread.bot_id, thread.thread_id)}
          >
            <!-- Bot avatar -->
            {#if thread.bot_avatar_path}
              <img
                src={thumbUrl(thread.bot_avatar_path, 50)}
                alt={thread.bot_name}
                class="rc-avatar"
              />
            {:else}
              <GeneratedAvatar name={thread.bot_name} size={44} />
            {/if}

            <!-- Content -->
            <div class="rc-content">
              <div class="rc-top">
                <span class="rc-name">{thread.bot_name}</span>
                {#if thread.bot_categories.length > 0}
                  <span class="rc-cat">{thread.bot_categories[0]}</span>
                {/if}
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

  /* ─── List ─── */
  .rc-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  /* ─── Card ─── */
  .rc-card {
    display: flex;
    align-items: stretch;
    background: var(--rc-bg-card);
    border: 1px solid var(--rc-border);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.15s ease;
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
  .rc-avatar {
    width: 44px;
    height: 44px;
    border-radius: 10px;
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
  .rc-cat {
    font-size: 10px;
    font-weight: 500;
    padding: 1px 7px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--rc-text) 5%, transparent);
    color: var(--rc-text-secondary);
    letter-spacing: 0.3px;
    white-space: nowrap;
    flex-shrink: 0;
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
