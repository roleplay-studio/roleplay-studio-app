<!-- FormFieldDemo.svelte -->
<script lang="ts">
  import FormField from '../../FormField.svelte';
  import Input from '../../Input.svelte';
  let v = $state('');
</script>

<div class="ff-stack">
  <FormField label="Bot name" hint="What users see in the bot list">
    <Input bind:value={v} placeholder="e.g. Aria" />
  </FormField>
  <FormField label="Required" error="Name is required">
    <Input value="" disabled />
  </FormField>
</div>

<style>
  .ff-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 320px;
  }
</style>
