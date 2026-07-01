<!-- BadgesDemo.svelte — Badge component, all variants + sizes -->
<script lang="ts">
  import Badge from '../../Badge.svelte';
</script>

<div class="bd-stack">
  <div class="bd-row">
    <span class="bd-label">Variants</span>
    <Badge variant="primary">Primary</Badge>
    <Badge variant="success">Success</Badge>
    <Badge variant="warning">Warning</Badge>
    <Badge variant="error">Error</Badge>
    <Badge variant="info">Info</Badge>
    <Badge variant="accent">Accent</Badge>
    <Badge variant="soft">Soft</Badge>
    <Badge variant="secondary">Secondary</Badge>
    <Badge variant="outline">Outline</Badge>
  </div>
  <div class="bd-row">
    <span class="bd-label">Sizes</span>
    <Badge size="sm" variant="primary">Small</Badge>
    <Badge size="md" variant="primary">Medium</Badge>
    <Badge size="lg" variant="primary">Large</Badge>
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
