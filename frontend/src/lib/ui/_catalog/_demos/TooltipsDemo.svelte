<!-- TooltipsDemo.svelte — Tooltip component, positions + variants -->
<script lang="ts">
  import Button from '../../Button.svelte';
  import Tooltip from '../../Tooltip.svelte';
</script>

<div class="bd-stack">
  <div class="bd-row">
    <span class="bd-label">Positions</span>
    <Tooltip text="I appear on top" position="top">
      <Button variant="secondary">Top</Button>
    </Tooltip>
    <Tooltip text="I appear on bottom" position="bottom">
      <Button variant="secondary">Bottom</Button>
    </Tooltip>
    <Tooltip text="I appear on left" position="left">
      <Button variant="secondary">Left</Button>
    </Tooltip>
    <Tooltip text="I appear on right" position="right">
      <Button variant="secondary">Right</Button>
    </Tooltip>
  </div>
  <div class="bd-row">
    <span class="bd-label">Variants</span>
    <Tooltip text="Default tooltip" variant="default">
      <Button variant="secondary">Default</Button>
    </Tooltip>
    <Tooltip text="Informational message" variant="info">
      <Button variant="info">Info</Button>
    </Tooltip>
    <Tooltip text="Something failed" variant="error">
      <Button variant="error">Error</Button>
    </Tooltip>
  </div>
</div>

<style>
  .bd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .bd-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
  }
  .bd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-width: 80px;
  }
</style>
