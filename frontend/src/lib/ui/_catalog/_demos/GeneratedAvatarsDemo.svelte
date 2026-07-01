<!-- GeneratedAvatarsDemo.svelte — 12 generated avatars at 3 sizes
     + size/shape variants, to show the deterministic-by-name system. -->
<script lang="ts">
  import GeneratedAvatar from '../../../ui/GeneratedAvatar.svelte';

  // 12 sample names — each will produce a unique gradient + face
  // because generateAvatar() hashes the name.
  const NAMES = [
    'Aria',
    'Luna',
    'Hermes',
    'Nova',
    'Sage',
    'Kai',
    'Mira',
    'Onyx',
    'Iris',
    'Rune',
    'Vex',
    'Zara',
  ];

  // Special cases worth demoing
  const EDGE_CASES = [
    { label: 'Empty name', name: '' },
    { label: 'Single char', name: 'X' },
    { label: 'Emoji name', name: '🌙' },
    { label: 'Long name', name: 'Bartholomew the Wise' },
  ];
</script>

<div class="gad-stack">
  <div class="gad-row">
    <span class="gad-label">Same name → same avatar (12 names, 64px)</span>
    <div class="gad-grid">
      {#each NAMES as n (n)}
        <div class="gad-cell">
          <GeneratedAvatar name={n} size={64} />
          <span class="gad-name">{n}</span>
        </div>
      {/each}
    </div>
  </div>

  <div class="gad-row">
    <span class="gad-label">Sizes (name = "Aria", 4 sizes)</span>
    <div class="gad-sizes">
      <GeneratedAvatar name="Aria" size={24} />
      <GeneratedAvatar name="Aria" size={32} />
      <GeneratedAvatar name="Aria" size={48} />
      <GeneratedAvatar name="Aria" size={80} />
    </div>
  </div>

  <div class="gad-row">
    <span class="gad-label">Shapes (name = "Luna", 48px)</span>
    <div class="gad-sizes">
      <GeneratedAvatar name="Luna" size={48} shape="circle" />
      <GeneratedAvatar name="Luna" size={48} shape="rounded" />
      <GeneratedAvatar name="Luna" size={48} shape="square" />
    </div>
  </div>

  <div class="gad-row">
    <span class="gad-label">Edge cases (48px)</span>
    <div class="gad-sizes">
      {#each EDGE_CASES as { label, name } (label)}
        <div class="gad-cell">
          <GeneratedAvatar {name} size={48} />
          <span class="gad-name">{label}</span>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .gad-stack {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .gad-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .gad-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .gad-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 12px;
  }
  .gad-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .gad-name {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-secondary);
  }
  .gad-sizes {
    display: flex;
    align-items: flex-end;
    gap: 16px;
  }
</style>
