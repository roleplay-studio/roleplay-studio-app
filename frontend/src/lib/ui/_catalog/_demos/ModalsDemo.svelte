<!-- ModalsDemo.svelte — Modal component, all sizes + open/close via button -->
<script lang="ts">
  import Button from '../../Button.svelte';
  import Modal from '../../Modal.svelte';

  let smOpen = $state(false);
  let mdOpen = $state(false);
  let lgOpen = $state(false);
  let footerOpen = $state(false);
</script>

<div class="md-stack">
  <div class="md-row">
    <Button variant="primary" onclick={() => (smOpen = true)}>Open SM</Button>
    <Button variant="primary" onclick={() => (mdOpen = true)}>Open MD</Button>
    <Button variant="primary" onclick={() => (lgOpen = true)}>Open LG</Button>
    <Button variant="primary" onclick={() => (footerOpen = true)}>With footer</Button>
  </div>
  <p class="md-hint">Press <kbd>Esc</kbd> or click outside to close.</p>
</div>

<Modal bind:open={smOpen} size="sm" title="Small modal">
  <p>A compact 400px-wide modal for short messages, confirmations, and small forms.</p>
</Modal>

<Modal bind:open={mdOpen} size="md" title="Default modal">
  <p>
    A 520px-wide modal — the workhorse of dialogs. Good for forms with a handful of fields,
    single-page content previews, and most standard interactions.
  </p>
  <p>It has padding, a title bar with a close button, and a flexible body region.</p>
</Modal>

<Modal bind:open={lgOpen} size="lg" title="Large modal">
  <p>A 672px-wide modal for richer content: multi-section forms, previews, or settings panels.</p>
  <p>Modal body uses our default font and line height, so it reads like the rest of the app.</p>
</Modal>

<Modal bind:open={footerOpen} size="md" title="Confirm action">
  <p>This action cannot be undone. Are you sure you want to proceed?</p>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (footerOpen = false)}>Cancel</Button>
    <Button variant="primary" onclick={() => (footerOpen = false)}>Confirm</Button>
  {/snippet}
</Modal>

<style>
  .md-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .md-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .md-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
  kbd {
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 8%, transparent);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    border-radius: 4px;
    padding: 1px 5px;
  }
  p {
    font-family: 'Maple Mono', monospace;
    font-size: 13px;
    color: var(--ray-text-secondary);
    line-height: 1.5;
    margin: 0 0 8px 0;
  }
  p:last-child {
    margin-bottom: 0;
  }
</style>
