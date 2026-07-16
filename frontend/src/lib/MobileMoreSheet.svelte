<!--
  MobileMoreSheet — bottom sheet that opens when the user taps the
  "More" slot in <MobileBottomNav>. Houses the destinations that
  don't fit in the bottom bar: Settings, Wizard, theme switcher,
  version info.

  Phase 1.4 of docs/MOBILE_PLAN.md. Simple overlay (no drag-to-dismiss
  yet — drag is Phase 3 when <BottomSheet> becomes reusable).

  Conventions:
    - Glass overlay (backdrop + blur) per DESIGN.md §Tooltip/Dropdown
    - Background = --ray-surface (light: white, dark: #101111)
    - Closes on backdrop click and Escape key
    - Focus trap: focus moves into the sheet on open
-->
<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';

  interface Props {
    onclose: () => void;
    open: boolean;
  }

  const { onclose, open }: Props = $props();

  function handleBackdropClick() {
    onclose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      onclose();
    }
  }

  function navigate(path: string) {
    window.location.hash = path === '/' ? '#/' : `#${path}`;
    onclose();
  }

  function setTheme(pref: 'dark' | 'light' | 'system') {
    // Lazy import to avoid SSR/test bundle cycles
    import('./theme').then((m) => {
      m.applyThemePreference(pref);
      onclose();
    });
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });

  // Focus the first interactive element when the sheet opens (a11y)
  $effect(() => {
    if (open) {
      tick().then(() => {
        const firstButton = document.querySelector<HTMLElement>(
          '.mms-content button, .mms-content [tabindex="0"]',
        );
        firstButton?.focus();
      });
    }
  });

  // Body scroll lock when open — prevents the page behind from scrolling
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
</script>

{#if open}
  <!-- Backdrop -->
  <div
    class="mms-backdrop"
    onclick={handleBackdropClick}
    onkeydown={(e) => e.key === 'Enter' && handleBackdropClick()}
    role="button"
    tabindex="-1"
    aria-label="Close menu"
  ></div>

  <!-- Sheet -->
  <div class="mms-root" role="dialog" aria-modal="true" aria-label="More options">
    <div class="mms-content">
      <div class="mms-handle" aria-hidden="true"></div>

      <nav class="mms-nav" aria-label="Secondary navigation">
        <button type="button" class="mms-link" onclick={() => navigate('/settings')}>
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><circle cx="12" cy="12" r="3" /><path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            /></svg
          >
          <span>Settings</span>
        </button>

        <button type="button" class="mms-link" onclick={() => navigate('/setup')}>
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><path
              d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"
            /><path d="m14 7 3 3" /><path d="M5 6v4" /><path d="M19 14v4" /><path
              d="M10 2v2"
            /><path d="M7 8H3" /><path d="M21 16h-4" /><path d="M11 3H9" /></svg
          >
          <span>Wizard</span>
        </button>
      </nav>

      <div class="mms-divider" role="presentation"></div>

      <div class="mms-theme" role="radiogroup" aria-label="Theme">
        <span class="mms-section-label">Theme</span>
        <div class="mms-theme-row">
          <button
            type="button"
            class="mms-theme-btn"
            onclick={() => setTheme('light')}
            aria-label="Light theme"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><circle cx="12" cy="12" r="5" /><path
                d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"
              /></svg
            >
            Light
          </button>
          <button
            type="button"
            class="mms-theme-btn"
            onclick={() => setTheme('dark')}
            aria-label="Dark theme"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg
            >
            Dark
          </button>
          <button
            type="button"
            class="mms-theme-btn"
            onclick={() => setTheme('system')}
            aria-label="System theme"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></svg
            >
            System
          </button>
        </div>
      </div>

      <div class="mms-footer">
        <span class="mms-version">v0.1.0</span>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Backdrop — same dark glass as Modal.svelte */
  .mms-backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    animation: mms-fade-in 0.18s ease;
  }

  .mms-root {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 61;
    background: var(--ray-overlay);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    /* Matches Modal radius per DESIGN.md §Shapes */
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      0 -4px 24px rgba(0, 0, 0, 0.3);
    padding-bottom: var(--safe-bottom, 0px);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    animation: mms-slide-up 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Only show at <768px (where MobileBottomNav exists). On larger
     viewports the Sidebar's nav covers these destinations. */
  @media (min-width: 768px) {
    .mms-root,
    .mms-backdrop {
      display: none;
    }
  }

  .mms-content {
    padding: 8px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }

  .mms-handle {
    width: 36px;
    height: 4px;
    background: var(--ray-border-strong);
    border-radius: 2px;
    margin: 8px auto 4px;
  }

  .mms-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mms-link {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    padding: 10px 12px;
    border: none;
    background: transparent;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-align: left;
    border-radius: 8px;
    cursor: pointer;
    transition:
      opacity 0.15s ease,
      background 0.15s ease;
  }

  .mms-link:hover {
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
  }

  .mms-link:focus-visible {
    outline: 2px solid var(--ray-blue);
    outline-offset: -2px;
  }

  .mms-divider {
    height: 1px;
    background: var(--ray-border-subtle);
    margin: 4px 0;
  }

  .mms-section-label {
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0 12px;
  }

  .mms-theme-row {
    display: flex;
    gap: 8px;
    padding: 0 12px;
  }

  .mms-theme-btn {
    flex: 1;
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border: 1px solid var(--ray-border);
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.25px;
    border-radius: 8px;
    cursor: pointer;
    transition:
      opacity 0.15s ease,
      background 0.15s ease;
  }

  .mms-theme-btn:hover {
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
    color: var(--ray-text);
  }

  .mms-theme-btn:focus-visible {
    outline: 2px solid var(--ray-blue);
    outline-offset: -2px;
  }

  .mms-footer {
    text-align: center;
    padding: 8px 0;
  }

  .mms-version {
    font-size: 10px;
    color: var(--ray-text-tertiary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    letter-spacing: 0.25px;
  }

  @keyframes mms-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes mms-slide-up {
    from {
      transform: translateY(100%);
    }
    to {
      transform: translateY(0);
    }
  }
</style>
