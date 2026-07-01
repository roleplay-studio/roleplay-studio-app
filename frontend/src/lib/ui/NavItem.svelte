<!-- NavItem — single nav row used by Sidebar (and any future nav
     list). Domain-agnostic: takes an icon (SVG markup), a label
     (already-translated text), an active flag, and an onclick.

     Collapsed mode hides the label via the `collapsed` prop, which
     the parent toggles based on its own state. -->

<script lang="ts">
  const {
    active = false,
    collapsed = false,
    icon,
    label,
    onclick,
  }: {
    active?: boolean;
    collapsed?: boolean;
    icon: string;
    label: string;
    onclick?: () => void;
  } = $props();
</script>

<button class="ni" class:ni-active={active} class:ni-collapsed={collapsed} {onclick} type="button">
  <span class="ni-icon">{@html icon}</span>
  {#if !collapsed}
    <span class="ni-label">{label}</span>
  {/if}
</button>

<style>
  .ni {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ni-text, var(--ray-text-secondary, #6e6e73));
    cursor: pointer;
    transition: all 0.12s ease;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-align: left;
    width: 100%;
  }
  .ni-collapsed {
    justify-content: center;
    padding: 8px;
  }
  .ni:hover {
    background: var(--ni-hover, rgba(0, 0, 0, 0.04));
    color: var(--ni-text-strong, var(--ray-text, #1d1d1f));
  }
  .ni-active {
    background: var(--ni-active-bg, rgba(0, 0, 0, 0.06));
    color: var(--ni-text-strong, var(--ray-text, #1d1d1f));
    font-weight: 600;
  }
  .ni-icon {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .ni-icon :global(svg) {
    width: 100%;
    height: 100%;
  }
  .ni-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
