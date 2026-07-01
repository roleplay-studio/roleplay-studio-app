<!-- Dropdown — Raycast-style popover dropdown with Svelte state -->
<script lang="ts">
  import { renderIcon } from './iconMap';
  const {
    align = 'start',
    class: className = '',
    items = [],
    label = '',
    onselect,
  }: {
    align?: 'end' | 'start';
    class?: string;
    items: { divider?: boolean; icon?: string; label: string; value: string }[];
    label?: string;
    onselect?: (value: string) => void;
  } = $props();

  let open = $state(false);

  function handleSelect(value: string) {
    open = false;
    if (onselect) onselect(value);
  }

  function toggle() {
    open = !open;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }
</script>

<div class="rd-wrap {className}" onkeydown={handleKeydown}>
  <button class="rd-trigger" onclick={toggle} aria-haspopup="true" aria-expanded={open}>
    {label}
    <span class="icon-wrapper">{@html renderIcon('chevron-down')}</span>
  </button>
  {#if open}
    <div class="rd-backdrop" onclick={() => (open = false)} role="presentation"></div>
    <div class="rd-panel {align === 'end' ? 'rd-end' : ''}" role="menu">
      {#each items as item, i (item.value || i)}
        {#if item.divider}
          <div class="rd-divider"></div>
        {:else}
          <button class="rd-item" role="menuitem" onclick={() => handleSelect(item.value)}>
            {#if item.icon}
              <span class="icon-wrapper">{@html renderIcon(item.icon)}</span>
            {/if}
            {item.label}
          </button>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .rd-wrap {
    position: relative;
    display: inline-flex;
  }

  /* ── Trigger button ── */
  .rd-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary, #9c9c9d);
    background: transparent;
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .rd-trigger:hover {
    color: var(--ray-text, #f9f9f9);
    border-color: var(--ray-border-strong, rgba(255, 255, 255, 0.1));
  }

  /* ── Backdrop ── */
  .rd-backdrop {
    position: fixed;
    inset: 0;
    z-index: 48;
  }

  /* ── Panel ── */
  .rd-panel {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    min-width: 160px;
    background: var(--ray-overlay, #1b1c1e);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    border-radius: 10px;
    z-index: 49;
    overflow: hidden;
    padding: 4px;
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      0 8px 32px rgba(0, 0, 0, 0.3);
  }
  .rd-end {
    left: auto;
    right: 0;
  }

  /* ── Item ── */
  .rd-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 10px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.1s ease;
    text-align: left;
  }
  .rd-item:hover {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
    color: var(--ray-text, #f9f9f9);
  }

  /* ── Divider ── */
  .rd-divider {
    height: 1px;
    margin: 2px 8px;
    background: var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
  }
</style>
