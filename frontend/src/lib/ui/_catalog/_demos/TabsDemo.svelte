<!-- TabsDemo.svelte — Tabs segmented control, with reactive state -->
<script lang="ts">
  import Tabs from '../../Tabs.svelte';

  let active = $state('overview');
</script>

<div class="td-stack">
  <Tabs
    activeTab={active}
    onchange={(id) => (active = id)}
    tabs={[
      { id: 'overview', label: 'Overview' },
      { id: 'specs', label: 'Specs' },
      { id: 'reviews', label: 'Reviews' },
      { id: 'related', label: 'Related' },
    ]}
  />

  <div class="td-panel">
    {#if active === 'overview'}
      <p>Overview tab — high-level summary, hero image, and key callouts.</p>
    {:else if active === 'specs'}
      <p>Specs tab — detailed technical specifications and parameters.</p>
    {:else if active === 'reviews'}
      <p>Reviews tab — user reviews, ratings, and feedback.</p>
    {:else if active === 'related'}
      <p>Related tab — similar items, recommendations, and cross-sells.</p>
    {/if}
  </div>
</div>

<style>
  .td-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .td-panel {
    padding: 16px 18px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 3%, transparent);
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    min-height: 80px;
  }
  p {
    font-family: 'Maple Mono', monospace;
    font-size: 13px;
    color: var(--ray-text-secondary);
    line-height: 1.5;
    margin: 0;
  }
</style>
