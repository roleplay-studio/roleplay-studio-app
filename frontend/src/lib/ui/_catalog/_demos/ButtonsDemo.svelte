<!-- ButtonsDemo.svelte — Button component, all variants + sizes + states -->
<script lang="ts">
  import Button from '../../Button.svelte';
  let count = $state(0);
</script>

<div class="bd-stack">
  <div class="bd-row">
    <span class="bd-label">Variants</span>
    <Button variant="primary">Primary</Button>
    <Button variant="secondary">Secondary</Button>
    <Button variant="outline">Outline</Button>
    <Button variant="ghost">Ghost</Button>
    <Button variant="soft">Soft</Button>
    <Button variant="text">Text</Button>
    <Button variant="error">Error</Button>
    <Button variant="info">Info</Button>
    <Button variant="success">Success</Button>
    <Button variant="warning">Warning</Button>
  </div>
  <div class="bd-row">
    <span class="bd-label">Sizes</span>
    <Button variant="primary" size="sm">Small</Button>
    <Button variant="primary" size="md">Medium</Button>
    <Button variant="primary" size="lg">Large</Button>
    <Button variant="primary" size="xl">XL</Button>
  </div>
  <div class="bd-row">
    <span class="bd-label">States</span>
    <Button variant="primary" disabled>Disabled</Button>
    <Button variant="primary" loading>Loading</Button>
    <Button variant="primary" onclick={() => count++}>Clicked {count}×</Button>
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
    gap: 8px;
    align-items: center;
  }
  .bd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-width: 70px;
  }
</style>
