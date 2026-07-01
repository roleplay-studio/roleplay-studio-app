<!-- InputsDemo.svelte — Input component with various states -->
<script lang="ts">
  import Input from '../../Input.svelte';
  let v1 = $state('');
  let v2 = $state('');
  let v3 = $state('');
</script>

<div class="id-stack">
  <Input bind:value={v1} label="Text Input" placeholder="Enter text..." />
  <Input bind:value={v2} label="With error" error="This field has an error" />
  <Input bind:value={v3} label="Disabled" disabled placeholder="Can't edit" />
</div>

<style>
  .id-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 320px;
  }
</style>
