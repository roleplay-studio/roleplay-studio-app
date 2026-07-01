<!-- LoadingDemo.svelte — Loading component, all types + sizes + with text -->
<script lang="ts">
  import Loading from '../../Loading.svelte';
</script>

<div class="bd-stack">
  <div class="bd-row">
    <span class="bd-label">Types</span>
    <Loading type="spinner" />
    <Loading type="dots" />
  </div>
  <div class="bd-row">
    <span class="bd-label">Sizes</span>
    <Loading type="spinner" size="xs" />
    <Loading type="spinner" size="sm" />
    <Loading type="spinner" size="md" />
    <Loading type="spinner" size="lg" />
    <Loading type="spinner" size="xl" />
  </div>
  <div class="bd-row">
    <span class="bd-label">With text</span>
    <Loading type="spinner" text="Loading bots..." />
    <Loading type="dots" text="Connecting..." />
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
    gap: 16px;
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
