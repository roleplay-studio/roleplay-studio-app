<!-- SelectsDemo.svelte -->
<script lang="ts">
  import Select from '../../Select.svelte';
  let v = $state('');
  const options = [
    { label: 'RolePlay', value: 'rp' },
    { label: 'Assistant', value: 'assistant' },
    { label: 'Agent', value: 'agent' },
  ];
</script>

<div class="sd-stack">
  <Select bind:value={v} {options} placeholder="Choose type..." />
  <Select bind:value={v} {options} />
</div>

<style>
  .sd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 320px;
  }
</style>
