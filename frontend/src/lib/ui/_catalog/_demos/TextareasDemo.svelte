<!-- TextareasDemo.svelte -->
<script lang="ts">
  import Textarea from '../../Textarea.svelte';
  let v = $state('');
</script>

<div class="td-stack">
  <Textarea bind:value={v} placeholder="Auto-growing..." />
  <Textarea bind:value={v} placeholder="Disabled" disabled />
</div>

<style>
  .td-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 320px;
  }
</style>
