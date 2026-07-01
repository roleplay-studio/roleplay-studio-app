<!-- ComponentFrame.svelte — wraps each catalog entry with title, anchor, and optional side-by-side legacy demo -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  let {
    children,
    legacyDemo,
    slug,
    title,
  }: {
    children?: Snippet;
    legacyDemo?: Snippet;
    slug: string;
    title: string;
  } = $props();
</script>

<article id={slug} class="cf-frame">
  <header class="cf-header">
    <h3 class="cf-title">{title}</h3>
    <a class="cf-anchor" href="#{slug}" aria-label="Link to {title}">🔗</a>
  </header>
  {#if legacyDemo}
    <div class="cf-side-by-side">
      <div class="cf-half">
        <div class="cf-label">Legacy (Raycast)</div>
        {@render legacyDemo()}
      </div>
      <div class="cf-half">
        <div class="cf-label">Component</div>
        {#if children}
          {@render children()}
        {/if}
      </div>
    </div>
  {:else}
    <div class="cf-demo">
      {#if children}
        {@render children()}
      {/if}
    </div>
  {/if}
</article>

<style>
  .cf-frame {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 20px;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border-card);
    border-radius: 12px;
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      var(--ray-shadow-inset) 0px 0px 0px 1px inset;
  }
  .cf-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .cf-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--ray-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .cf-anchor {
    text-decoration: none;
    opacity: 0.5;
    font-size: 14px;
    transition: opacity 0.12s ease;
  }
  .cf-anchor:hover {
    opacity: 1;
  }
  .cf-demo {
    padding: 16px;
    background: var(--ray-bg);
    border-radius: 8px;
  }
  .cf-side-by-side {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .cf-half {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    background: var(--ray-bg);
    border-radius: 8px;
  }
  .cf-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
</style>
