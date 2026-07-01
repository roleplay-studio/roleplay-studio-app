<!-- CatalogSection.svelte — group header for a catalog section -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    children,
    description,
    title,
  }: {
    children?: Snippet;
    description?: string;
    title: string;
  } = $props();
</script>

<section class="cs-section">
  <header class="cs-header">
    <h2 class="cs-title">{title}</h2>
    {#if description}
      <p class="cs-desc">{description}</p>
    {/if}
  </header>
  <div class="cs-content">
    {#if children}
      {@render children()}
    {/if}
  </div>
</section>

<style>
  .cs-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 32px;
  }
  .cs-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .cs-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--ray-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .cs-desc {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .cs-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
</style>
