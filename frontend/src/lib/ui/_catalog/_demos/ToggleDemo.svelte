<!-- ToggleDemo.svelte -->
<script lang="ts">
  import Toggle from '../../Toggle.svelte';
  let on = $state(true);
  let off = $state(false);
</script>

<div class="td-row">
  <label class="td-label">
    <Toggle bind:checked={on} /> Enabled
  </label>
  <label class="td-label">
    <Toggle bind:checked={off} /> Disabled
  </label>
  <label class="td-label">
    <Toggle checked={true} disabled /> Locked
  </label>
</div>

<style>
  .td-row {
    display: flex;
    gap: 16px;
    align-items: center;
    flex-wrap: wrap;
  }
  .td-label {
    display: flex;
    gap: 6px;
    align-items: center;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text);
  }
</style>
