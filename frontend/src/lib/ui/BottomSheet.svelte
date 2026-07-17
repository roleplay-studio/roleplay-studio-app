<!--
  BottomSheet — reusable bottom-sheet overlay.

  Phase 3.1 of docs/MOBILE_PLAN.md. Replaces the bespoke MobileMoreSheet
  with a general-purpose component that can host any content (Settings
  tabs, ThreadTree, More menu, etc.).

  Features:
    - open / onclose props (same as MobileMoreSheet)
    - dismiss on backdrop click, Escape key, or downward drag (>120px)
    - max-height: 90vh, defaults to 'auto' but exposes a `snapTo` prop
      ('small' | 'medium' | 'large') for future half-sheet use cases
    - glass overlay (backdrop + blur) per DESIGN.md §Tooltip/Dropdown
    - body scroll lock while open
    - focus moves into sheet on open (a11y)
    - hidden at >=768px (mobile-only — desktop gets Sidebar/side panels)

  Conventions:
    - Glass background: --ray-overlay
    - Top corners 14px radius (DESIGN.md §Shapes `lg`)
    - Snap-points via CSS variable --sheet-height (default: 'auto')
    - Slide-up animation matches Modal scale-in timing

  Usage:
    <BottomSheet open={isOpen} onclose={() => isOpen = false}>
      <h2>Title</h2>
      <p>Content</p>
    </BottomSheet>
-->
<script lang="ts">
  import { onDestroy, onMount, type Snippet, tick } from 'svelte';

  interface Props {
    /** Optional accessible label for the dialog (defaults to 'Menu'). */
    ariaLabel?: string;
    /** Snippet for sheet content. */
    children?: Snippet;
    /** Whether drag-to-dismiss is enabled (default true). */
    draggable?: boolean;
    onclose: () => void;
    open: boolean;
    /** Snap point: small (40vh), medium (70vh), large (90vh), or auto. */
    snapTo?: 'auto' | 'large' | 'medium' | 'small';
  }

  const {
    ariaLabel = 'Menu',
    children,
    draggable = true,
    onclose,
    open,
    snapTo = 'auto',
  }: Props = $props();

  // ── Snap-point height (CSS var) ─────────────────────────────────
  const snapHeight = $derived(
    snapTo === 'small'
      ? '40vh'
      : snapTo === 'medium'
        ? '70vh'
        : snapTo === 'large'
          ? '90vh'
          : 'auto',
  );

  // ── Drag-to-dismiss ──────────────────────────────────────────────
  // Pointer-down on the handle starts a drag; if the user moves the
  // pointer up by >120px before releasing, the sheet closes. If they
  // drag up (negative dy) we ignore — the sheet is already at its
  // snap-point, no overscroll on purpose.
  let sheetEl: HTMLDivElement | undefined = $state();
  let dragStartY: null | number = $state(null);
  let dragOffsetY = $state(0);
  let isDragging = $state(false);

  function handlePointerDown(e: PointerEvent) {
    if (!draggable) return;
    dragStartY = e.clientY;
    isDragging = true;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }
  function handlePointerMove(e: PointerEvent) {
    if (!isDragging || dragStartY === null) return;
    const dy = e.clientY - dragStartY;
    dragOffsetY = Math.max(0, dy); // only allow downward drag
  }
  function handlePointerUp() {
    if (!isDragging) return;
    isDragging = false;
    if (dragOffsetY > 120) {
      onclose();
    }
    dragStartY = null;
    dragOffsetY = 0;
  }

  // ── Backdrop / Escape close ──────────────────────────────────────
  function handleBackdropClick() {
    onclose();
  }
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) onclose();
  }

  // ── Lifecycle: body scroll lock, focus on open ──────────────────
  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });
  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });

  $effect(() => {
    if (typeof document === 'undefined') return;
    if (open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prev;
      };
    }
  });

  $effect(() => {
    if (open) {
      tick().then(() => {
        sheetEl
          ?.querySelector<HTMLElement>('button, [tabindex="0"], input, textarea, select')
          ?.focus();
      });
    }
  });
</script>

{#if open}
  <div
    class="bs-backdrop"
    onclick={handleBackdropClick}
    onkeydown={(e) => e.key === 'Enter' && handleBackdropClick()}
    role="button"
    tabindex="-1"
    aria-label="Close"
  ></div>

  <div
    bind:this={sheetEl}
    class="bs-root"
    class:bs-dragging={isDragging}
    role="dialog"
    aria-modal="true"
    aria-label={ariaLabel}
    style="--sheet-height: {snapHeight}; --drag-offset: {dragOffsetY}px;"
  >
    <!-- Drag handle — also the touch target for swipe-to-dismiss -->
    {#if draggable}
      <div
        class="bs-handle"
        aria-hidden="true"
        onpointerdown={handlePointerDown}
        onpointermove={handlePointerMove}
        onpointerup={handlePointerUp}
        onpointercancel={handlePointerUp}
      >
        <span class="bs-handle-bar"></span>
      </div>
    {/if}

    <!-- Content — caller injects via children snippet -->
    <div class="bs-content">
      {@render children?.()}
    </div>
  </div>
{/if}

<style>
  /* ── Backdrop ── */
  .bs-backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    animation: bs-fade-in 0.18s ease;
  }

  /* ── Sheet root ── */
  .bs-root {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 61;
    background: var(--ray-overlay);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      0 -4px 24px rgba(0, 0, 0, 0.3);
    padding-bottom: var(--safe-bottom, 0px);
    max-height: min(var(--sheet-height, auto), 90vh);
    display: flex;
    flex-direction: column;
    /* Apply drag offset for visual feedback during swipe */
    transform: translateY(var(--drag-offset, 0px));
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    animation: bs-slide-up 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .bs-dragging {
    transition: none; /* no easing during active drag */
  }

  /* Hide at >=768px — desktop uses Sidebar/side panels instead */
  @media (min-width: 768px) {
    .bs-backdrop,
    .bs-root {
      display: none;
    }
  }

  /* ── Handle ── */
  .bs-handle {
    width: 100%;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    touch-action: none; /* required for pointer events on iOS */
    flex-shrink: 0;
  }
  .bs-handle:active {
    cursor: grabbing;
  }
  .bs-handle-bar {
    width: 36px;
    height: 4px;
    background: var(--ray-border-strong);
    border-radius: 2px;
  }

  /* ── Content area ── */
  .bs-content {
    padding: 4px 16px 16px;
    overflow-y: auto;
    flex: 1 1 auto;
    min-height: 0; /* flexbox overflow fix */
  }

  /* ── Animations ── */
  @keyframes bs-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes bs-slide-up {
    from {
      transform: translateY(100%);
    }
    to {
      transform: translateY(0);
    }
  }

  /* Respect reduced-motion preference */
  @media (prefers-reduced-motion: reduce) {
    .bs-backdrop,
    .bs-root {
      animation-duration: 0.01s !important;
    }
  }
</style>
