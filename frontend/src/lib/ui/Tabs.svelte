<!-- Tabs — Raycast-style segmented tabs with pill indicator -->
<script lang="ts">
  import { renderIcon } from './iconMap';
  const {
    activeTab = '',
    class: className = '',
    onchange,
    tabs = [],
  }: {
    activeTab: string;
    class?: string;
    onchange?: (id: string) => void;
    tabs: { icon?: string; id: string; label: string }[];
  } = $props();

  function handleClick(id: string) {
    if (onchange) onchange(id);
  }
</script>

<div class="rt-tabs {className}">
  {#each tabs as tab (tab.id)}
    <button
      class="rt-tab {tab.id === activeTab ? 'rt-active' : ''}"
      onclick={() => handleClick(tab.id)}
      type="button"
    >
      {#if tab.icon}
        <span class="icon-wrapper">{@html renderIcon(tab.icon)}</span>
      {/if}
      {tab.label}
    </button>
  {/each}
</div>

<style>
  .rt-tabs {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 3px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 4%, transparent);
    border-radius: 10px;
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
  }
  .rt-tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary, #9c9c9d);
    background: transparent;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }
  .rt-tab:hover {
    color: var(--ray-text, #f9f9f9);
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
  }
  .rt-tab.rt-active {
    color: var(--ray-text, #f9f9f9);
    background: var(--ray-surface, #101111);
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      0 1px 3px rgba(0, 0, 0, 0.15);
  }
</style>
