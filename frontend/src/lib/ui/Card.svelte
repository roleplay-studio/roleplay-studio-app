<!-- Card — Raycast-style card with double-ring shadow -->
<!-- Usage: <Card>Content</Card> -->
<!-- With slots: <Card><svelte:fragment slot="header">Title</svelte:fragment>Body</Card> -->
<script lang="ts">
  const {
    bordered = true,
    children,
    class: className = '',
    footer,
    header,
    hover = false,
    padding = true,
  }: {
    bordered?: boolean;
    children?: import('svelte').Snippet;
    class?: string;
    footer?: import('svelte').Snippet;
    header?: import('svelte').Snippet;
    hover?: boolean;
    padding?: boolean;
  } = $props();
</script>

<div
  class="rc-card {padding ? 'rc-padded' : ''} {bordered ? 'rc-bordered' : ''} {hover
    ? 'rc-hover'
    : ''} {className}"
>
  {#if header}
    <div class="rc-header">
      {@render header()}
    </div>
  {/if}

  {#if children}
    {@render children()}
  {/if}

  {#if footer}
    <div class="rc-footer">
      {@render footer()}
    </div>
  {/if}
</div>

<style>
  .rc-card {
    background: var(--ray-surface, #101111);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      var(--ray-shadow-inset, rgb(7, 8, 10)) 0px 0px 0px 1px inset;
  }
  .rc-bordered {
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
  }
  .rc-padded {
    padding: 20px;
  }
  .rc-hover {
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
  }
  .rc-hover:hover {
    border-color: var(--ray-border-strong, rgba(255, 255, 255, 0.1));
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      0 4px 16px rgba(0, 0, 0, 0.2);
  }
  .rc-header {
    padding-bottom: 12px;
    border-bottom: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    margin-bottom: 12px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-weight: 600;
    font-size: 15px;
    color: var(--ray-text, #f9f9f9);
    letter-spacing: 0.2px;
  }
  .rc-footer {
    padding-top: 12px;
    border-top: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    margin-top: 12px;
  }
</style>
