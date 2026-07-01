<!-- MessageContextMenu — right-click context menu for a chat message bubble.
     Renders nothing when position is null. Auto-closes on Esc / outside click /
     scroll / resize. Edge-flips upward when it would overflow the viewport. -->
<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';

  import type { Message } from './api';

  import { currentLang, t } from './i18n';

  let {
    msg,
    onclose,
    onedit,
    position,
  }: {
    msg: Message;
    onclose: () => void;
    onedit?: (m: Message) => void;
    position: null | { x: number; y: number };
  } = $props();

  let lang = $state('en');
  let copied = $state(false);
  let copyTimer: null | ReturnType<typeof setTimeout> = null;
  let menuEl: HTMLDivElement | undefined = $state();
  let adjustedPos = $state<null | { x: number; y: number }>(null);

  // Mirror the current language for reactive label swaps (Copy → Copied!).
  $effect(() => {
    const unsub = currentLang.subscribe((v) => (lang = v));
    return unsub;
  });

  async function recalcPosition() {
    if (!position) {
      adjustedPos = null;
      return;
    }
    await tick();
    const h = menuEl?.offsetHeight ?? 0;
    const margin = 8;
    if (typeof window === 'undefined') {
      adjustedPos = position;
      return;
    }
    const wouldOverflow = position.y + h + margin > window.innerHeight;
    adjustedPos = wouldOverflow
      ? { x: position.x, y: Math.max(margin, position.y - h) }
      : { x: position.x, y: position.y };
  }

  $effect(() => {
    // Track position. Set adjustedPos synchronously so the menu can
    // render immediately, then refine after the DOM has measured
    // its own height (for edge-flip).
    const pos = position;
    if (!pos) {
      adjustedPos = null;
      return;
    }
    adjustedPos = pos;
    recalcPosition();
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }

  function handleWindowClick(e: MouseEvent) {
    if (!menuEl) return;
    if (!(e.target instanceof Node)) return;
    if (menuEl.contains(e.target)) return;
    onclose();
  }

  function handleScrollOrResize() {
    if (position) onclose();
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('mousedown', handleWindowClick, true);
    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
  });

  onDestroy(() => {
    if (typeof window === 'undefined') return;
    window.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('mousedown', handleWindowClick, true);
    window.removeEventListener('scroll', handleScrollOrResize, true);
    window.removeEventListener('resize', handleScrollOrResize);
    if (copyTimer) clearTimeout(copyTimer);
  });

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(msg.content);
      copied = true;
      if (copyTimer) clearTimeout(copyTimer);
      copyTimer = setTimeout(() => {
        copied = false;
        copyTimer = null;
      }, 1500);
    } catch {
      // Clipboard API may be unavailable (e.g. insecure context).
      // Fail silently — the user can still right-click → standard copy.
    }
  }

  function handleEdit() {
    onedit?.(msg);
    onclose();
  }
</script>

{#if position && adjustedPos}
  <div
    class="ctx-menu"
    bind:this={menuEl}
    style="left: {adjustedPos.x}px; top: {adjustedPos.y}px;"
    role="menu"
  >
    <button class="ctx-item" type="button" role="menuitem" onclick={handleCopy}>
      <svg
        class="ico"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
      </svg>
      <span>{copied ? t('message.menu.copied', lang) : t('message.menu.copy', lang)}</span>
    </button>
    <button class="ctx-item" type="button" role="menuitem" onclick={handleEdit}>
      <svg
        class="ico"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path>
        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"></path>
      </svg>
      <span>{t('message.menu.edit', lang)}</span>
    </button>
  </div>
{/if}

<style>
  .ctx-menu {
    position: fixed;
    z-index: 1000;
    min-width: 168px;
    padding: 4px;
    background: color-mix(in srgb, var(--ray-bg, #1b1c1e) 92%, transparent);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    box-shadow:
      0 0 0 1px rgba(0, 0, 0, 0.4),
      0 8px 24px rgba(0, 0, 0, 0.45);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .ctx-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 7px 10px;
    border: 0;
    border-radius: 4px;
    background: transparent;
    color: var(--ray-text, #e5e5e7);
    font: inherit;
    font-size: 13px;
    letter-spacing: 0.2px;
    text-align: left;
    cursor: pointer;
    transition: background 0.08s ease;
  }
  .ctx-item:hover,
  .ctx-item:focus-visible {
    background: color-mix(in srgb, var(--ray-text, #ffffff) 8%, transparent);
    outline: none;
  }
  .ctx-item .ico {
    width: 14px;
    height: 14px;
    opacity: 0.8;
    flex-shrink: 0;
  }
</style>
