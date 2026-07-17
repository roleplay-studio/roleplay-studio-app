<!--
  OfflineBanner — thin notification strip that appears at the top of
  the viewport when navigator.onLine becomes false (e.g. user goes
  into airplane mode, or the LAN/WiFi drops).

  Phase 5.4 of docs/MOBILE_PLAN.md. Listens to 'online' / 'offline'
  window events. Disappears automatically when connectivity returns.

  Conventions:
    - Glass overlay (backdrop-blur) per DESIGN.md §Tooltip/Dropdown
    - Uses --ray-yellow for the warning accent (per the semantic palette)
    - Always visible at the top of the viewport, above any content
    - Hidden via aria-hidden + display: none when online
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  let online = $state(true);

  function handleOnline() {
    online = true;
  }
  function handleOffline() {
    online = false;
  }

  onMount(() => {
    // Sync initial state — navigator.onLine reflects the current
    // connectivity at boot time, not just the most recent event.
    online = navigator.onLine;
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
  });

  onDestroy(() => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  });
</script>

{#if !online}
  <div class="offline-banner" role="status" aria-live="polite">
    <svg
      class="offline-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <line x1="1" y1="1" x2="23" y2="23" />
      <path
        d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"
      />
    </svg>
    <span class="offline-text">Offline — showing cached content</span>
  </div>
{/if}

<style>
  .offline-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 70; /* above everything except critical modals */
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 8px 16px;
    background: color-mix(in srgb, var(--ray-yellow) 18%, transparent);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid color-mix(in srgb, var(--ray-yellow) 30%, transparent);
    color: var(--ray-yellow);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.25px;
    text-align: center;
    /* Slide-in animation */
    animation: ob-slide-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .offline-icon {
    flex-shrink: 0;
  }

  .offline-text {
    /* Truncate gracefully on very narrow viewports */
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  @keyframes ob-slide-in {
    from {
      transform: translateY(-100%);
    }
    to {
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .offline-banner {
      animation-duration: 0.01s !important;
    }
  }
</style>
