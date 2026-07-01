<!-- Alert — notification/alert component using FlyonUI alert classes -->
<!-- Usage: <Alert variant="success" icon="circle-check">Saved!</Alert> -->
<!-- Dismissible: <Alert variant="warning" dismissible onclose={() => console.log('closed')}>Careful!</Alert> -->
<script lang="ts">
  import { renderIcon } from './iconMap';
  const {
    children,
    class: className = '',
    dismissible = false,
    icon = '',
    onclose,
    variant = 'info',
  }: {
    children?: import('svelte').Snippet;
    class?: string;
    dismissible?: boolean;
    icon?: string;
    onclose?: () => void;
    variant?: 'error' | 'info' | 'primary' | 'success' | 'warning';
  } = $props();

  let visible = $state(true);

  function handleClose() {
    visible = false;
    onclose?.();
  }
</script>

{#if visible}
  <div
    class="alert alert-{variant} {dismissible ? 'alert-dismissible' : ''} {className}"
    role="alert"
  >
    {#if icon}
      <span class="icon-wrapper">{@html renderIcon(icon, 20)}</span>
    {/if}

    {#if children}
      <div class="alert-body">
        {@render children()}
      </div>
    {/if}

    {#if dismissible}
      <button class="alert-close" onclick={handleClose} aria-label="Close">
        <span class="icon-wrapper">{@html renderIcon('x')}</span>
      </button>
    {/if}
  </div>
{/if}

<style>
  .alert {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .alert-body {
    flex: 1 1 auto;
    min-width: 0;
  }
  .alert-close {
    margin-left: auto;
    flex: 0 0 auto;
    background: none;
    border: none;
    cursor: pointer;
    color: inherit;
    opacity: 0.7;
    padding: 2px;
    border-radius: 4px;
    transition: opacity 0.15s ease;
  }
  .alert-close:hover {
    opacity: 1;
  }
  .icon-wrapper {
    flex: 0 0 auto;
    display: inline-flex;
  }
</style>
