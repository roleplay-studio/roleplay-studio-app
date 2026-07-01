<!-- NotificationModalsDemo.svelte — 6 semantic variants of NotificationModal
     (success, info, warning, error, celebration, help). Each variant
     shows a different icon and pastel circle background. -->
<script lang="ts">
  import Button from '../../Button.svelte';
  import NotificationModal from '../../NotificationModal.svelte';

  let openIndex = $state<null | number>(null);

  const VARIANTS = [
    { label: 'Show success', message: 'Bot saved successfully!', variant: 'success' },
    {
      label: 'Show info',
      message: 'A new version is available. Refresh to update.',
      variant: 'info',
    },
    { label: 'Show warning', message: 'Your subscription expires in 3 days.', variant: 'warning' },
    {
      label: 'Show error',
      message: 'Failed to connect to the server. Please try again.',
      variant: 'error',
    },
    {
      label: 'Show celebration',
      message: 'You unlocked 1000 chat messages!',
      variant: 'celebration',
    },
    {
      label: 'Show help',
      message: 'Need help getting started? Check out our docs.',
      variant: 'help',
    },
  ] as const;

  type VariantName = (typeof VARIANTS)[number]['variant'];
</script>

<div class="nmd-stack">
  <div class="nmd-row">
    {#each VARIANTS as v, i (v.variant)}
      <Button
        variant={v.variant === 'error'
          ? 'error'
          : v.variant === 'warning'
            ? 'warning'
            : v.variant === 'info'
              ? 'info'
              : v.variant === 'success'
                ? 'success'
                : 'primary'}
        onclick={() => (openIndex = i)}
      >
        {v.label}
      </Button>
    {/each}
  </div>
</div>

{#each VARIANTS as v, i (v.variant)}
  <NotificationModal
    show={openIndex === i}
    message={v.message}
    variant={v.variant as VariantName}
    onclose={() => (openIndex = null)}
  />
{/each}

<style>
  .nmd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .nmd-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
