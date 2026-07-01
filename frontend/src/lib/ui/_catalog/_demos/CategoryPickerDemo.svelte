<!-- CategoryPickerDemo.svelte — pill grid for selecting multiple categories -->
<script lang="ts">
  import CategoryPicker from '../../../CategoryPicker.svelte';

  const ALL = ['Anime', 'Sci-Fi', 'Fantasy', 'Romance', 'Horror', 'Mystery', 'Comedy', 'Drama'];
  let selected = $state<string[]>(['Sci-Fi', 'Fantasy']);
</script>

<div class="cpd-stack">
  <CategoryPicker allCategories={ALL} {selected} onchange={(c: string[]) => (selected = c)} />
  <p class="cpd-state">Selected ({selected.length}): {selected.join(', ') || '(none)'}</p>
</div>

<style>
  .cpd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .cpd-state {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
