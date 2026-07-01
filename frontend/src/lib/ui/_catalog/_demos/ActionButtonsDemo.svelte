<!-- ActionButtonsDemo.svelte — ActionButtons chip group with click handler -->
<script lang="ts">
  import ActionButtons from '../../ActionButtons.svelte';
</script>

<div class="ab-stack">
  <div class="ab-row">
    <span class="ab-label">Default</span>
    <ActionButtons
      actions={['Continue', 'Roll dice', 'Inventory']}
      onaction={(text) => console.log('[ab] action:', text)}
    />
  </div>
  <div class="ab-row">
    <span class="ab-label">Empty</span>
    <ActionButtons actions={[]} />
  </div>
  <div class="ab-row">
    <span class="ab-label">Many</span>
    <ActionButtons
      actions={[
        'Look around',
        'Talk to merchant',
        'Open chest',
        'Save game',
        'Check map',
        'Cast spell',
      ]}
    />
  </div>
</div>

<style>
  .ab-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .ab-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ab-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
</style>
