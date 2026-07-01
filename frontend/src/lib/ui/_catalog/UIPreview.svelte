<!-- _catalog/UIPreview.svelte — /ui-kit page shell.
     Renders every CatalogEntry inside a ComponentFrame, grouped by
     CatalogGroup. Demos load via dynamic import on mount. -->
<script lang="ts">
  import type { Component } from 'svelte';

  import CatalogSection from './_components/CatalogSection.svelte';
  import CodeSnippet from './_components/CodeSnippet.svelte';
  import ComponentFrame from './_components/ComponentFrame.svelte';
  import PropsTable from './_components/PropsTable.svelte';
  import ThemeSwitcher from './_components/ThemeSwitcher.svelte';
  import { CATALOG, type CatalogEntry } from './_data/catalog';

  const FOUNDATIONS = $derived(CATALOG.filter((e) => e.group === 'foundations'));
  const ATOMIC = $derived(CATALOG.filter((e) => e.group === 'atomic'));
  const COMPOSITE = $derived(CATALOG.filter((e) => e.group === 'composite'));

  // Lazy-loaded component per entry slug.
  let loaded = $state<Record<string, Component | null>>({});

  async function loadEntry(entry: CatalogEntry) {
    if (loaded[entry.slug]) return;
    try {
      const mod = await entry.demo();
      loaded = { ...loaded, [entry.slug]: mod.default };
    } catch (e) {
      console.error(`[ui-catalog] failed to load demo for ${entry.slug}:`, e);
    }
  }

  // Pre-load all entries on mount. For Phase 1 (4 entries) the bundle
  // cost is negligible; if Phase 2/3 demos bloat the initial chunk we
  // can switch to on-intersection lazy loading.
  $effect(() => {
    CATALOG.forEach(loadEntry);
  });

  /** Render the legacy (Raycast inline) snippet for a given entry.
   *  Returns the inline markup string, or null if no legacy demo for
   *  this entry. Only Button + Input have a `.ray-btn` / `.ray-input`
   *  legacy variant defined in app.css; Modal/Card have `.ray-card` but
   *  the demo files render the new component directly. */
  function legacyMarkup(entry: CatalogEntry): null | string {
    if (!entry.hasLegacyDemo) return null;
    switch (entry.slug) {
      case 'button':
        return (
          '<button class="ray-btn primary">Primary</button> ' +
          '<button class="ray-btn">Default</button> ' +
          '<button class="ray-btn danger">Danger</button>'
        );
      case 'input':
        return (
          '<input class="ray-input" placeholder="Legacy input..." /> ' +
          '<input class="ray-input" placeholder="Disabled" disabled />'
        );
      default:
        return null;
    }
  }
</script>

<div class="uikit-page">
  <header class="uk-header">
    <div>
      <h1 class="uk-title">UI Kit</h1>
      <p class="uk-subtitle">All reusable components in one place · {CATALOG.length} blocks</p>
    </div>
    <ThemeSwitcher />
  </header>

  <!-- ═══ Foundations ═══ -->
  <CatalogSection
    title="Foundations"
    description="Design tokens from app.css — colors, typography, spacing"
  >
    {#each FOUNDATIONS as entry (entry.slug)}
      <ComponentFrame slug={entry.slug} title={entry.title}>
        {#if loaded[entry.slug]}
          <svelte:component this={loaded[entry.slug]} />
        {/if}
      </ComponentFrame>
    {/each}
  </CatalogSection>

  <!-- ═══ Atomic ═══ -->
  <CatalogSection title="Atomic" description="Reusable building blocks from src/lib/ui/">
    {#each ATOMIC as entry (entry.slug)}
      <ComponentFrame slug={entry.slug} title={entry.title}>
        {#snippet legacyDemo()}
          {#if entry.hasLegacyDemo && legacyMarkup(entry)}
            <!-- eslint-disable-next-line svelte/no-at-html-tags -->
            {@html legacyMarkup(entry)}
          {/if}
        {/snippet}
        {#if loaded[entry.slug]}
          <svelte:component this={loaded[entry.slug]} />
        {/if}
        {#if entry.props && entry.props.length > 0}
          <PropsTable props={entry.props} />
        {/if}
        {#each entry.snippets as snip (snip.title)}
          <CodeSnippet title={snip.title} lang={snip.lang} code={snip.code} />
        {/each}
      </ComponentFrame>
    {/each}
  </CatalogSection>

  <!-- ═══ Composite ═══ -->
  {#if COMPOSITE.length > 0}
    <CatalogSection title="Composite" description="Domain-aware reusable blocks from src/lib/">
      {#each COMPOSITE as entry (entry.slug)}
        <ComponentFrame slug={entry.slug} title={entry.title}>
          {#if loaded[entry.slug]}
            <svelte:component this={loaded[entry.slug]} />
          {/if}
          {#if entry.props && entry.props.length > 0}
            <PropsTable props={entry.props} />
          {/if}
          {#each entry.snippets as snip (snip.title)}
            <CodeSnippet title={snip.title} lang={snip.lang} code={snip.code} />
          {/each}
        </ComponentFrame>
      {/each}
    </CatalogSection>
  {/if}
</div>

<style>
  .uikit-page {
    padding: 32px 48px;
    color: var(--ray-text);
    max-width: 1100px;
    margin: 0 auto;
  }
  .uk-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 36px;
    gap: 24px;
  }
  .uk-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 28px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--ray-text);
  }
  .uk-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 4px 0 0;
  }
  @media (max-width: 768px) {
    .uikit-page {
      padding: 20px 16px;
    }
    .uk-header {
      flex-direction: column;
    }
  }
</style>
