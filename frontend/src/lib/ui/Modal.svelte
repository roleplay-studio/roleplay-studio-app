<!-- Modal — Raycast-style modal with blur backdrop, animation -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    children,
    class: _className = '',
    footer,
    onclose,
    open = $bindable(false),
    size = 'md',
    title = '',
  }: {
    children?: Snippet;
    class?: string;
    footer?: Snippet;
    onclose?: () => void;
    open?: boolean;
    size?: 'lg' | 'md' | 'sm' | 'xl';
    title?: string;
  } = $props();

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      open = false;
      onclose?.();
    }
  }

  function close() {
    open = false;
    onclose?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="rm-overlay" class:rm-visible={open} onclick={close} role="presentation"></div>

<div class="rm-wrap" class:rm-visible={open} aria-hidden={!open} role="dialog" onclick={close}>
  <div
    class="rm-dialog rm-{size} {_className}"
    class:rm-visible={open}
    onclick={(e) => e.stopPropagation()}
  >
    <!-- Header -->
    <div class="rm-header">
      <h3 class="rm-title">{title}</h3>
      <button class="rm-close" onclick={close} aria-label="Close">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"
          ></line></svg
        >
      </button>
    </div>

    <!-- Body -->
    <div class="rm-body">
      {#if children}
        {@render children()}
      {/if}
    </div>

    <!-- Footer -->
    {#if footer}
      <div class="rm-footer">
        {@render footer()}
      </div>
    {/if}
  </div>
</div>

<style>
  /* ─── Overlay with blur ─── */
  .rm-overlay {
    position: fixed;
    inset: 0;
    z-index: 98;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    opacity: 0;
    transition: opacity 0.2s ease;
    pointer-events: none;
  }
  .rm-overlay.rm-visible {
    opacity: 1;
    pointer-events: auto;
  }

  /* ─── Wrapper (centering) ─── */
  .rm-wrap {
    position: fixed;
    inset: 0;
    z-index: 99;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }
  .rm-wrap.rm-visible {
    opacity: 1;
    pointer-events: auto;
  }

  /* ─── Dialog ─── */
  .rm-dialog {
    background: var(--ray-surface, #1b1c1e);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    border-radius: 14px;
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      0 16px 48px rgba(0, 0, 0, 0.3);
    width: 100%;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    transform: scale(0.95) translateY(8px);
    transition:
      transform 0.2s ease,
      opacity 0.2s ease;
    opacity: 0;
  }
  .rm-dialog.rm-visible {
    transform: scale(1) translateY(0);
    opacity: 1;
  }

  /* ─── Sizes ─── */
  .rm-sm {
    max-width: 400px;
  }
  .rm-md {
    max-width: 520px;
  }
  .rm-lg {
    max-width: 672px;
  }
  .rm-xl {
    max-width: 896px;
  }

  /* ─── Header ─── */
  .rm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px 0;
  }
  .rm-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: var(--ray-text, #f9f9f9);
    letter-spacing: 0.2px;
    margin: 0;
  }
  .rm-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    cursor: pointer;
    transition: all 0.12s ease;
    flex-shrink: 0;
  }
  .rm-close:hover {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 8%, transparent);
    color: var(--ray-text, #f9f9f9);
  }

  /* ─── Body ─── */
  .rm-body {
    padding: 16px 20px 20px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    color: var(--ray-text-secondary, #9c9c9d);
    letter-spacing: 0.2px;
    line-height: 1.6;
  }

  /* ─── Footer ─── */
  .rm-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 0 20px 16px;
  }
</style>
