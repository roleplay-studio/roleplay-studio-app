<!-- Badge — Raycast-style pill badge -->
<!-- Usage: <Badge variant="primary">Tag</Badge> -->
<script lang="ts">
  const {
    children,
    class: className = '',
    size = 'md',
    variant = 'primary',
  }: {
    children?: import('svelte').Snippet;
    class?: string;
    size?: 'lg' | 'md' | 'sm';
    variant?:
      | 'accent'
      | 'error'
      | 'info'
      | 'outline'
      | 'primary'
      | 'secondary'
      | 'soft'
      | 'success'
      | 'warning';
  } = $props();
</script>

<span
  class="rb rb-{variant} rb-{size} {className}"
  style={variant === 'outline'
    ? 'border:1px solid var(--ray-border-strong,rgba(0,0,0,0.1));color:var(--ray-text-secondary,#6e6e73)'
    : ''}
>
  {#if children}
    {@render children()}
  {/if}
</span>

<style>
  .rb {
    display: inline-flex;
    align-items: center;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-weight: 500;
    letter-spacing: 0.25px;
    white-space: nowrap;
    border-radius: 86px;
    transition: all 0.12s ease;
  }
  .rb-sm {
    font-size: 10px;
    padding: 2px 8px;
    gap: 3px;
  }
  .rb-md {
    font-size: 11px;
    padding: 3px 10px;
    gap: 4px;
  }
  .rb-lg {
    font-size: 13px;
    padding: 5px 14px;
    gap: 5px;
  }

  /* ─── Variants ─── */
  .rb-primary {
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 12%, transparent);
    color: var(--ray-blue, hsl(202, 100%, 67%));
  }
  .rb-success {
    background: color-mix(in srgb, var(--ray-green, #5fc992) 12%, transparent);
    color: var(--ray-green, #5fc992);
  }
  .rb-warning {
    background: color-mix(in srgb, #f59e0b 12%, transparent);
    color: #f59e0b;
  }
  .rb-error {
    background: color-mix(in srgb, var(--ray-red, #ff6363) 12%, transparent);
    color: var(--ray-red, #ff6363);
  }
  .rb-info {
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }
  .rb-accent {
    background: color-mix(in srgb, #8b5cf6 12%, transparent);
    color: #8b5cf6;
  }
  .rb-soft {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }
  .rb-secondary {
    background: color-mix(in srgb, var(--ray-text-secondary, #9c9c9d) 12%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }
  .rb-outline {
    background: transparent;
  }
</style>
