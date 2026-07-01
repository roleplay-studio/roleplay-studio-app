<!-- Button — Raycast-style button with pill shape and opacity hover -->
<script lang="ts">
  import type { Component, Snippet } from 'svelte';

  import { renderIcon } from './iconMap';

  const {
    children,
    class: className = '',
    disabled = false,
    href = '',
    icon,
    loading = false,
    onclick,
    size = 'md',
    type = 'button',
    variant = 'primary',
  }: {
    children?: Snippet;
    class?: string;
    disabled?: boolean;
    href?: string;
    icon?: Component<{ class?: string }> | string;
    loading?: boolean;
    onclick?: (e: MouseEvent) => void;
    size?: 'lg' | 'md' | 'sm' | 'xl';
    type?: 'button' | 'reset' | 'submit';
    variant?:
      | 'accent'
      | 'error'
      | 'ghost'
      | 'info'
      | 'outline'
      | 'pill'
      | 'primary'
      | 'secondary'
      | 'soft'
      | 'success'
      | 'text'
      | 'warning';
  } = $props();

  const btnClass = $derived.by(() => {
    let cls = 'rb';
    cls += ` rb-${variant}`;
    cls += ` rb-${size}`;
    if (disabled) cls += ' rb-disabled';
    if (className) cls += ` ${className}`;
    return cls;
  });
</script>

{#if href}
  <a {href} class={btnClass} role="button" {onclick}>
    {#if loading}
      <span class="rb-spinner" aria-label="loading"></span>
    {/if}
    {#if icon}
      {#if typeof icon === 'string'}
        <span class="icon-wrapper">{@html renderIcon(icon)}</span>
      {:else}
        <svelte:component this={icon} class="size-4" />
      {/if}
    {/if}
    {#if children}
      {@render children()}
    {/if}
  </a>
{:else}
  <button {type} {disabled} class={btnClass} {onclick}>
    {#if loading}
      <span class="rb-spinner" aria-label="loading"></span>
    {/if}
    {#if icon}
      {#if typeof icon === 'string'}
        <span class="icon-wrapper">{@html renderIcon(icon)}</span>
      {:else}
        <svelte:component this={icon} class="size-4" />
      {/if}
    {/if}
    {#if children}
      {@render children()}
    {/if}
  </button>
{/if}

<style>
  /* ── Raycast Button Base ── */
  .rb {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.2px;
    white-space: nowrap;
    border: none;
    cursor: pointer;
    transition: opacity 0.15s ease;
    text-decoration: none;
    line-height: 1;
  }

  /* ── Sizes ── */
  .rb-sm {
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
  }
  .rb-md {
    padding: 8px 16px;
    border-radius: 8px;
  }
  .rb-lg {
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
  }
  .rb-xl {
    padding: 12px 24px;
    border-radius: 10px;
    font-size: 15px;
  }

  /* ── Primary — pill with white/semi-transparent bg ── */
  .rb-primary {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 90%, transparent);
    color: white;
    border-radius: 86px;
    box-shadow:
      rgba(255, 255, 255, 0.1) 0px 1px 0px 0px inset,
      rgba(0, 0, 0, 0.15) 0px -1px 0px 0px inset;
  }
  .rb-primary:hover {
    opacity: 0.85;
  }

  /* ── CTA pill — Raycast download button style ── */
  .rb-pill {
    background: hsla(0, 0%, 100%, 0.85);
    color: #18191a;
    border-radius: 86px;
    font-weight: 600;
    letter-spacing: 0.3px;
  }
  .rb-pill:hover {
    background: hsl(0, 0%, 100%);
  }

  /* ── Secondary — bordered rectangle ── */
  .rb-secondary {
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    border-radius: 8px;
    box-shadow: rgba(0, 0, 0, 0.03) 0px 2px 4px;
  }
  .rb-secondary:hover {
    color: var(--ray-text, #f9f9f9);
    border-color: var(--ray-border-strong, rgba(255, 255, 255, 0.1));
    opacity: 1;
  }

  /* ── Ghost — invisible until hover ── */
  .rb-ghost {
    background: transparent;
    color: var(--ray-text-tertiary, #6a6b6c);
    border-radius: 86px;
    box-shadow: rgba(255, 255, 255, 0.05) 0px 1px 0px 0px inset;
  }
  .rb-ghost:hover {
    color: var(--ray-text, #f9f9f9);
    opacity: 0.8;
  }

  /* ── Outline ── */
  .rb-outline {
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    border: 1px solid var(--ray-border-strong, rgba(255, 255, 255, 0.1));
    border-radius: 8px;
  }
  .rb-outline:hover {
    color: var(--ray-text, #f9f9f9);
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
  }

  /* ── Soft ── */
  .rb-soft {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 12%, transparent);
    color: var(--ray-accent, #8b5cf6);
    border-radius: 8px;
  }
  .rb-soft:hover {
    opacity: 0.8;
  }

  /* ── Text — no background ── */
  .rb-text {
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    border-radius: 6px;
  }
  .rb-text:hover {
    color: var(--ray-text, #f9f9f9);
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
  }

  /* ── Semantic variants ── */
  .rb-accent {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 15%, transparent);
    color: var(--ray-accent, #8b5cf6);
    border-radius: 8px;
  }
  .rb-accent:hover {
    opacity: 0.8;
  }
  .rb-info {
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 12%, transparent);
    color: var(--ray-blue, hsl(202, 100%, 67%));
    border-radius: 8px;
  }
  .rb-info:hover {
    opacity: 0.8;
  }
  .rb-success {
    background: color-mix(in srgb, var(--ray-green, #5fc992) 12%, transparent);
    color: var(--ray-green, #5fc992);
    border-radius: 8px;
  }
  .rb-success:hover {
    opacity: 0.8;
  }
  .rb-warning {
    background: color-mix(in srgb, var(--ray-yellow, #f59e0b) 12%, transparent);
    color: var(--ray-yellow, #f59e0b);
    border-radius: 8px;
  }
  .rb-warning:hover {
    opacity: 0.8;
  }
  .rb-error {
    background: color-mix(in srgb, var(--ray-red, #ff6363) 12%, transparent);
    color: var(--ray-red, #ff6363);
    border-radius: 8px;
  }
  .rb-error:hover {
    opacity: 0.8;
  }

  /* ── Disabled ── */
  .rb-disabled {
    opacity: 0.4;
    cursor: not-allowed;
    pointer-events: none;
  }

  /* ── Loading spinner ── */
  .rb-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: rb-spin 0.6s linear infinite;
  }
  @keyframes rb-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
