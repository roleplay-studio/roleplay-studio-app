<!-- FoundationsPaletteDemo.svelte — surface/neko/roleplay-studio color swatches -->
<script lang="ts">
  const SWATCHES: { name: string; var: string }[] = [
    { name: 'surface-50', var: '--color-surface-50' },
    { name: 'surface-100', var: '--color-surface-100' },
    { name: 'surface-300', var: '--color-surface-300' },
    { name: 'surface-500', var: '--color-surface-500' },
    { name: 'surface-700', var: '--color-surface-700' },
    { name: 'surface-900', var: '--color-surface-900' },
    { name: 'neko-300', var: '--color-neko-300' },
    { name: 'neko-500', var: '--color-neko-500' },
    { name: 'roleplay-studio-500', var: '--color-roleplay-studio-500' },
    { name: 'roleplay-studio-700', var: '--color-roleplay-studio-700' },
  ];
</script>

<div class="fp-grid">
  {#each SWATCHES as s (s.name)}
    <div class="fp-swatch">
      <div class="fp-color" style="background: var({s.var});"></div>
      <code class="fp-name">{s.name}</code>
    </div>
  {/each}
</div>

<style>
  .fp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
  }
  .fp-swatch {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .fp-color {
    width: 100%;
    height: 60px;
    border-radius: 8px;
    border: 1px solid var(--ray-border-subtle);
  }
  .fp-name {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 10px;
    color: var(--ray-text-secondary);
  }
</style>
