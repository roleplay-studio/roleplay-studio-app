<!-- AlertsDemo.svelte — Alert component, all variants + dismissible + icon -->
<script lang="ts">
  import Alert from '../../Alert.svelte';
</script>

<div class="ad-stack">
  <div class="ad-group">
    <span class="ad-label">Variants</span>
    <Alert variant="info">Info — Helpful context for the user.</Alert>
    <Alert variant="success">Success — Operation completed.</Alert>
    <Alert variant="warning">Warning — Proceed with care.</Alert>
    <Alert variant="error">Error — Something went wrong.</Alert>
    <Alert variant="primary">Primary — Highlighted message.</Alert>
  </div>
  <div class="ad-group">
    <span class="ad-label">With icon</span>
    <Alert variant="success" icon="circle-check">Saved to library</Alert>
    <Alert variant="error" icon="circle-x">Connection lost</Alert>
    <Alert variant="warning" icon="triangle-alert">Storage almost full</Alert>
  </div>
  <div class="ad-group">
    <span class="ad-label">Dismissible</span>
    <Alert variant="info" dismissible>Click × to close me</Alert>
    <Alert variant="warning" dismissible icon="triangle-alert">Dismissible with icon</Alert>
  </div>
</div>

<style>
  .ad-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .ad-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ad-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
</style>
