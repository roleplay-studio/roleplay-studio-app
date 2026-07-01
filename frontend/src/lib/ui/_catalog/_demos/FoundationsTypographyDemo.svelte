<!-- FoundationsTypographyDemo.svelte — weight + size scale -->
<script lang="ts">
  const WEIGHTS: { label: string; weight: number }[] = [
    { label: 'Thin 100', weight: 100 },
    { label: 'Light 300', weight: 300 },
    { label: 'Regular 400', weight: 400 },
    { label: 'Medium 500', weight: 500 },
    { label: 'Semibold 600', weight: 600 },
    { label: 'Bold 700', weight: 700 },
  ];
  const SCALE: { label: string; px: number }[] = [
    { label: 'caption', px: 11 },
    { label: 'small', px: 12 },
    { label: 'body', px: 13 },
    { label: 'body-lg', px: 14 },
    { label: 'h4', px: 15 },
    { label: 'h3', px: 18 },
    { label: 'h2', px: 22 },
    { label: 'h1', px: 28 },
  ];
</script>

<div class="ft-stack">
  <div>
    <h4 class="ft-subhead">Weight scale</h4>
    {#each WEIGHTS as w (w.label)}
      <div class="ft-row" style="font-weight: {w.weight};">{w.label}</div>
    {/each}
  </div>
  <div>
    <h4 class="ft-subhead">Size scale</h4>
    {#each SCALE as s (s.label)}
      <div class="ft-row ft-size" style="font-size: {s.px}px;">{s.label} · {s.px}px</div>
    {/each}
  </div>
</div>

<style>
  .ft-stack {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .ft-subhead {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 8px;
  }
  .ft-row {
    font-family: 'Maple Mono', monospace;
    color: var(--ray-text);
    padding: 2px 0;
  }
</style>
