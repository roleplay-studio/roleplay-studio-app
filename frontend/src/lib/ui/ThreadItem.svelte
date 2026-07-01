<!-- ThreadItem — single row in ThreadDrawer. Owns the rename UI but
     NOT the rename state (parent owns renamingThreadId + renameValue
     and passes them down). Domain-agnostic: takes a Thread object
     and a formatted time string. -->

<script lang="ts">
  import type { Thread } from '../api';

  let {
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
    <div class="ti-top">
      <p class="ti-name">{thread.name}</p>
      <button
        class="ti-dots"
        onclick={(e) => {
          e.stopPropagation();
          ondotsclick?.(e, thread.id);
        }}
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
    <div class="ti-bottom">
      {#if thread.persona_name}
        <span class="ti-persona">{thread.persona_name}</span>
      {/if}
      <span class="ti-time">{timeLabel}</span>
    </div>
  {/if}
</div>

<style>
  .ti {
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.12s ease;
    border: 1px solid transparent;
  }
  .ti:hover {
    background: var(--ti-hover, rgba(0, 0, 0, 0.03));
  }
  .ti-selected {
    background: var(--ti-selected, rgba(99, 102, 241, 0.08));
    border-color: var(--ti-selected-border, rgba(99, 102, 241, 0.18));
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
    color: var(--ti-text, #1d1d1f);
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
  .ti-bottom {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
    font-size: 11px;
    color: var(--ti-text-tertiary, #86868b);
  }
  .ti-persona {
    font-weight: 500;
  }
  .ti-time {
    margin-left: auto;
  }
  .ti-rename {
    padding: 2px 0;
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
