<!-- DeleteConfirmModalsDemo.svelte — delete confirmation modal with 3 langs -->
<script lang="ts">
  import DeleteConfirmModal from '../../../DeleteConfirmModal.svelte';
  import Button from '../../../ui/Button.svelte';

  let lang = $state<'de' | 'en' | 'ja'>('en');
  let open = $state(false);
</script>

<div class="dcm-stack">
  <div class="dcm-row">
    <span class="dcm-label">Language</span>
    <div class="dcm-lang-row">
      <Button
        variant={lang === 'en' ? 'primary' : 'secondary'}
        size="sm"
        onclick={() => (lang = 'en')}>EN</Button
      >
      <Button
        variant={lang === 'de' ? 'primary' : 'secondary'}
        size="sm"
        onclick={() => (lang = 'de')}>DE</Button
      >
      <Button
        variant={lang === 'ja' ? 'primary' : 'secondary'}
        size="sm"
        onclick={() => (lang = 'ja')}>JA</Button
      >
    </div>
  </div>
  <div class="dcm-row">
    <span class="dcm-label">Open</span>
    <Button variant="error" onclick={() => (open = true)}>Show delete dialog</Button>
  </div>
  <p class="dcm-hint">
    Modal uses t('delete_confirm.*', lang). Press Esc or click outside to close.
  </p>
</div>

<DeleteConfirmModal
  {lang}
  show={open}
  oncancel={() => (open = false)}
  onconfirm={() => (open = false)}
/>

<style>
  .dcm-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .dcm-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .dcm-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-width: 100px;
  }
  .dcm-lang-row {
    display: flex;
    gap: 6px;
  }
  .dcm-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
