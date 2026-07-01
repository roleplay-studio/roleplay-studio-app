<!-- NavItemsDemo.svelte — Sidebar nav item, expanded vs collapsed, with/without active state -->
<script lang="ts">
  import NavItem from '../../../ui/NavItem.svelte';
  import { logOnly } from '../_mocks/callbacks';

  const CHAT_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>';
  const BOTS_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>';
  const onClick = logOnly('nav-click');

  let active = $state(false);
</script>

<div class="nid-stack">
  <div class="nid-row">
    <span class="nid-label">Expanded (default)</span>
    <div class="nid-frame">
      <NavItem icon={CHAT_SVG} label="Чаты" onclick={onClick} />
      <NavItem icon={BOTS_SVG} label="Боты" active onclick={onClick} />
    </div>
  </div>
  <div class="nid-row">
    <span class="nid-label">Collapsed (label hidden)</span>
    <div class="nid-frame nid-frame-collapsed">
      <NavItem icon={CHAT_SVG} label="Чаты" collapsed onclick={onClick} />
      <NavItem icon={BOTS_SVG} label="Боты" collapsed active onclick={onClick} />
    </div>
  </div>
  <div class="nid-row">
    <span class="nid-label">Interactive (click to toggle active)</span>
    <div class="nid-frame">
      <NavItem icon={CHAT_SVG} label="Click me" {active} onclick={() => (active = !active)} />
    </div>
  </div>
</div>

<style>
  .nid-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .nid-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .nid-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .nid-frame {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    padding: 8px;
    background: var(--ray-bg-card, #ffffff);
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-width: 220px;
  }
  .nid-frame-collapsed {
    max-width: 60px;
  }
</style>
