<!-- SidebarsDemo.svelte — Sidebar with both expanded/collapsed states + mock current route -->
<script lang="ts">
  import Sidebar from '../../../Sidebar.svelte';
  import { sidebarOpen } from '../../../stores/sidebar';
</script>

<div class="sbd-stack">
  <div class="sbd-row">
    <span class="sbd-label">Expanded (default)</span>
    <div class="sbd-frame sbd-frame-wide">
      <Sidebar currentRoute="/ui-kit" />
    </div>
  </div>
  <div class="sbd-row">
    <span class="sbd-label">Collapsed (icon-only, hover brand to re-expand)</span>
    <div class="sbd-frame sbd-frame-narrow">
      <Sidebar currentRoute="/ui-kit" />
      <button
        class="ray-btn primary"
        onclick={() => sidebarOpen.set(true)}
        style="position:absolute;top:8px;right:8px;z-index:50"
      >
        Re-expand
      </button>
    </div>
  </div>
  <p class="sbd-hint">
    Sidebar is fixed-position in the real app. In this demo we wrap it in a narrow frame so the
    layout is contained. Clicking a nav button would re-route the app (by design) — see
    Sidebar.handleNav.
  </p>
</div>

<style>
  .sbd-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .sbd-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sbd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .sbd-frame {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    overflow: hidden;
    height: 360px;
    position: relative;
  }
  .sbd-frame-wide {
    width: 100%;
  }
  .sbd-frame-narrow {
    width: 100px;
  }
  .sbd-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
