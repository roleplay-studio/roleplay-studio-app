<!-- EditMessageModalsDemo.svelte — large modal with textarea + save/cancel footer -->
<script lang="ts">
  import EditMessageModal from '../../../EditMessageModal.svelte';
  import Button from '../../../ui/Button.svelte';
  import { logOnly } from '../_mocks/callbacks';

  let open = $state(false);
  const onsave = logOnly<(t: string) => void>('save-edited');
  const onclose = logOnly('close');
</script>

<div class="emm-stack">
  <Button variant="primary" onclick={() => (open = true)}>Edit message</Button>
  <p class="emm-hint">
    Large modal with a 10-row textarea. Save button is disabled while the textarea is empty.
  </p>
</div>

<EditMessageModal
  show={open}
  content="The old message text. Click save to fire the onsave callback with the new text."
  onsave={(t) => {
    onsave(t);
    open = false;
  }}
  {onclose}
  lang="en"
/>

<style>
  .emm-stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .emm-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
