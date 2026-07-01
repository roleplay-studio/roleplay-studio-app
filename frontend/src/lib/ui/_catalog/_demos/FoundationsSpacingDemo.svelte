<!-- FoundationsSpacingDemo.svelte — spacing + radius scale -->
<script lang="ts">
  const SCALE = [4, 8, 12, 16, 20, 24, 32, 40, 48, 64];
  const RADII: { name: string; val: string }[] = [
    { name: 'rounded-none', val: '0px' },
    { name: 'rounded-sm', val: '4px' },
    { name: 'rounded-md', val: '8px' },
    { name: 'rounded-lg', val: '12px' },
    { name: 'rounded-xl', val: '14px' },
    { name: 'rounded-pill', val: '86px' },
  ];
</script>

<div class="fs-stack">
  <div>
    <h4 class="fs-subhead">Spacing (px)</h4>
    {#each SCALE as n (n)}
      <div class="fs-row">
        <div class="fs-bar" style="width: {n}px;"></div>
        <code>{n}px</code>
      </div>
    {/each}
  </div>
  <div>
    <h4 class="fs-subhead">Border radius</h4>
    <div class="fs-radius-grid">
      {#each RADII as r (r.name)}
        <div class="fs-radius">
          <div class="fs-radius-box" style="border-radius: {r.val};"></div>
          <code>{r.name}</code>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .fs-stack {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .fs-subhead {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 8px;
  }
  .fs-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 0;
  }
  .fs-bar {
    height: 12px;
    background: var(--ray-accent);
    border-radius: 2px;
  }
  .fs-row code {
    font-family: 'Geist Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-secondary);
  }
  .fs-radius-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .fs-radius {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: center;
  }
  .fs-radius-box {
    width: 56px;
    height: 56px;
    background: var(--ray-accent);
    opacity: 0.6;
  }
  .fs-radius code {
    font-family: 'Geist Mono', monospace;
    font-size: 10px;
    color: var(--ray-text-secondary);
  }
</style>
