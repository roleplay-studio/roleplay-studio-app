<!-- ThreadItem — single row in ThreadDrawer. Owns the rename UI but
     NOT the rename state (parent owns renamingThreadId + renameValue
     and passes them down). Domain-agnostic: takes a Thread object
     and a formatted time string.

     Phase-1: enriched to show persona avatar, message count, and the
     last assistant message's short_content (preferred over the raw
     ``content`` preview). See the backend commit
     ``feat(api): enrich ThreadDTO with preview fields`` for the data
     contract this consumes. -->
<script lang="ts">
  import { avatarUrl, type Thread } from '../api';
  import { t } from '../i18n';
  import { GeneratedAvatar } from './index';

  let {
    lang = 'en',
    oncancelrename,
    oncontextmenu,
    ondotsclick,
    onrename,
    onselect,
    renameValue = $bindable(''),
    renaming = false,
    selected = false,
    thread,
    timeLabel,
  }: {
    lang?: string;
    oncancelrename?: (id: number) => void;
    oncontextmenu?: (e: MouseEvent, id: number) => void;
    ondotsclick?: (e: MouseEvent, id: number) => void;
    onrename?: (id: number, name: string) => void;
    onselect?: (id: number) => void;
    renameValue?: string;
    renaming?: boolean;
    selected?: boolean;
    thread: Thread;
    timeLabel: string;
  } = $props();

  let inputEl = $state<HTMLInputElement | null>(null);

  $effect(() => {
    if (renaming) inputEl?.focus();
  });

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      onrename?.(thread.id, renameValue);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      oncancelrename?.(thread.id);
    }
  }

  function handleRenameBlur() {
    onrename?.(thread.id, renameValue);
  }

  // Preview-source precedence (mirrors the backend contract on
  // ``list_for_bot_with_preview``): short_content first (already
  // structured for the list-row slot by the Summarizer), then
  // summary fallback (only when summary is set — typically for
  // older threads before the Summarizer was attached).
  const previewText = $derived.by(() => {
    if (thread.last_message_preview) return thread.last_message_preview;
    if (thread.summary) return thread.summary;
    return '';
  });
  const hasPreview = $derived(previewText.length > 0);

  // Localised message-count label. We carry three forms per locale
  // (one / other / zero) rather than relying on Intl.PluralRules
  // because the codebase ships a custom `t()` helper that doesn't
  // implement ICU plural categories — this keeps the i18n contract
  // consistent with the rest of the project.
  const messageCountLabel = $derived.by(() => {
    const n = thread.message_count;
    if (n === 0) return t('thread_items.message_count_zero', lang);
    if (n === 1) return t('thread_items.message_count_one', lang);
    return t('thread_items.message_count_other', lang).replace('{n}', String(n));
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="ti"
  class:ti-selected={selected}
  onclick={() => onselect?.(thread.id)}
  oncontextmenu={(e) => oncontextmenu?.(e, thread.id)}
>
  {#if renaming}
    <div class="ti-rename" onclick={(e) => e.stopPropagation()}>
      <input
        bind:this={inputEl}
        bind:value={renameValue}
        onkeydown={handleRenameKeydown}
        onblur={handleRenameBlur}
        class="ti-rename-input"
      />
    </div>
  {:else}
    <!-- Persona avatar (28×28). Always rendered even without persona —
         fallback is the GeneratedAvatar placeholder. The avatar
         anchors the row visually and matches the i18n persona-name
         label below. -->
    <div class="ti-avatar">
      {#if thread.persona_avatar_path}
        <img src={avatarUrl(thread.persona_avatar_path)} alt="" class="ti-avatar-img" />
      {:else}
        <GeneratedAvatar name={thread.persona_name ?? thread.name} size={28} />
      {/if}
    </div>

    <div class="ti-body">
      <div class="ti-top">
        <p class="ti-name text-rp-text-tertiary">{thread.name}</p>
        <button
          class="ti-dots"
          onclick={(e) => {
            e.stopPropagation();
            ondotsclick?.(e, thread.id);
          }}
          aria-label="Thread actions"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="12" r="1"></circle><circle
              cx="12"
              cy="19"
              r="1"
            ></circle></svg
          >
        </button>
      </div>
      <div class="ti-meta">
        {#if thread.persona_name}
          <span class="ti-persona">{thread.persona_name}</span>
          <span class="ti-meta-sep">·</span>
        {/if}
        <span class="ti-count">{messageCountLabel}</span>
        <span class="ti-time">{timeLabel}</span>
      </div>
      {#if hasPreview}
        <p class="ti-preview">{previewText}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .ti {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.12s ease;
    border: 1px solid transparent;
    align-items: flex-start;
  }
  .ti:hover {
    background: var(--ti-hover, rgba(0, 0, 0, 0.03));
  }
  .ti-selected {
    background: var(--ti-selected, rgba(99, 102, 241, 0.08));
    border-color: var(--ti-selected-border, rgba(99, 102, 241, 0.18));
  }

  /* Persona avatar — sized to anchor the row without dominating. */
  .ti-avatar {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    overflow: hidden;
    flex-shrink: 0;
    background: var(--ti-bg, #ffffff);
    margin-top: 1px;
  }
  .ti-avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .ti-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .ti-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .ti-name {
    flex: 1;
    margin: 0;
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ti-dots {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--ti-text-tertiary, #86868b);
    cursor: pointer;
    opacity: 0;
    transition: all 0.12s ease;
  }
  .ti:hover .ti-dots,
  .ti-selected .ti-dots {
    opacity: 1;
  }
  .ti-dots:hover {
    background: var(--ti-dots-hover, rgba(0, 0, 0, 0.06));
    color: var(--ti-text, #1d1d1f);
  }

  /* Meta line: persona • N сообщ. · timeLabel. Two pieces of text
     info on a single line because the row is height-constrained; the
     count badge is the most-actionable signal so it sits left of the
     timestamp. */
  .ti-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--ti-text-tertiary, #86868b);
    min-width: 0;
  }
  .ti-persona {
    font-weight: 500;
    color: var(--ti-text-secondary, #6e6e73);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 80px;
  }
  .ti-meta-sep {
    color: var(--ti-text-tertiary, #86868b);
  }
  .ti-count {
    font-feature-settings: 'tnum' 1;
    flex-shrink: 0;
  }
  .ti-time {
    margin-left: auto;
    flex-shrink: 0;
    font-size: 10.5px;
  }

  /* Preview line — single line clamp at the row's bottom; hides when
     there's no content (don't render an empty paragraph that adds
     1.4 line-height for nothing). */
  .ti-preview {
    margin: 0;
    font-size: 11.5px;
    line-height: 1.4;
    color: var(--ti-text-secondary, #6e6e73);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    letter-spacing: 0.1px;
  }

  .ti-rename {
    padding: 2px 0;
    grid-column: 1 / -1;
  }
  .ti-rename-input {
    width: 100%;
    padding: 4px 6px;
    font-size: 13px;
    font-family: inherit;
    color: var(--ti-text, #1d1d1f);
    background: var(--ti-bg, #ffffff);
    border: 1px solid var(--ti-selected-border, rgba(99, 102, 241, 0.4));
    border-radius: 4px;
    outline: none;
  }
  .ti-rename-input:focus {
    border-color: var(--ti-selected-border-strong, #6366f1);
  }
</style>
