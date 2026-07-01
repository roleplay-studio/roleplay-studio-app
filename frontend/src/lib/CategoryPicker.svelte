<!-- CategoryPicker — Raycast-style pill grid for selecting categories -->
<script lang="ts">
  let {
    allCategories = [],
    onchange,
    selected = [],
  }: {
    allCategories?: string[];
    onchange?: (categories: string[]) => void;
    selected?: string[];
  } = $props();

  function toggle(cat: string) {
    if (selected.includes(cat)) {
      onchange?.(selected.filter((c) => c !== cat));
    } else {
      onchange?.([...selected, cat]);
    }
  }
</script>

<div class="cp-field">
  <label class="cp-label">Categories</label>
  <div class="cp-grid">
    {#each allCategories as cat (cat)}
      <button
        class="cp-pill"
        class:selected={selected.includes(cat)}
        onclick={() => toggle(cat)}
        type="button"
      >
        {cat}
      </button>
    {/each}
  </div>
</div>

<style>
  :root {
    --cp-text: #1d1d1f;
    --cp-text-secondary: #6e6e73;
    --cp-border: rgba(0, 0, 0, 0.06);
    --cp-border-strong: rgba(0, 0, 0, 0.1);
    --cp-blue: hsl(211, 100%, 50%);
  }
  :root.dark {
    --cp-text: #f9f9f9;
    --cp-text-secondary: #9c9c9d;
    --cp-border: rgba(255, 255, 255, 0.06);
    --cp-border-strong: rgba(255, 255, 255, 0.1);
    --cp-blue: hsl(202, 100%, 67%);
  }

  .cp-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .cp-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--cp-text-secondary);
    letter-spacing: 0.2px;
  }
  .cp-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .cp-pill {
    padding: 5px 14px;
    border-radius: 86px;
    border: 1px solid var(--cp-border);
    background: transparent;
    color: var(--cp-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .cp-pill:hover {
    border-color: var(--cp-border-strong);
    color: var(--cp-text);
  }
  .cp-pill.selected {
    background: color-mix(in srgb, var(--cp-blue) 12%, transparent);
    border-color: color-mix(in srgb, var(--cp-blue) 30%, transparent);
    color: var(--cp-blue);
  }
</style>
