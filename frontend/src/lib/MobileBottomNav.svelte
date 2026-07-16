<!--
  MobileBottomNav — bottom navigation bar for mobile devices (<768px).

  Six slots:
    1. Dashboard    /#/
    2. Chat         /#/chat
    3. Bots         /#/bots
    4. Personas     /#/personas
    5. UI Kit       /#/ui-kit
    6. More         opens MobileMoreSheet (settings + wizard + theme)

  Phase 1.3 of docs/MOBILE_PLAN.md. Visible only on viewports <768px.
  Replaces the persistent <Sidebar> at small viewports (Sidebar is
  still rendered at >=768px — see Phase 1.6 of MOBILE_PLAN.md).

  Conventions (see DESIGN.md):
    - Maple Mono font, 12px caption weight for labels
    - Active slot uses --ray-text + subtle bg, inactive uses --ray-text-tertiary
    - 44×44px touch targets (Apple HIG / Material 3 minimum)
    - Safe-area inset respected via env(safe-area-inset-bottom)
    - Glass overlay: bg + backdrop-blur
    - Hover state is opacity: 0.8 (DESIGN.md §Hover)
-->
<script lang="ts">
  import { currentLang, t } from './i18n';

  type NavKey = 'bots' | 'chat' | 'dashboard' | 'more' | 'personas' | 'uiKit';

  interface Props {
    currentRoute: string;
    onMoreClick?: () => void;
  }

  const { currentRoute, onMoreClick }: Props = $props();

  const slots: { icon: string; key: NavKey; labelKey: string; path: string }[] = [
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12L12 4l9 8"/><path d="M5 10v10h14V10"/></svg>',
      key: 'dashboard',
      labelKey: 'nav.dashboard',
      path: '/',
    },
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>',
      key: 'chat',
      labelKey: 'nav.chat',
      path: '/chat',
    },
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>',
      key: 'bots',
      labelKey: 'nav.bots',
      path: '/bots',
    },
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      key: 'personas',
      labelKey: 'nav.personas',
      path: '/personas',
    },
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
      key: 'uiKit',
      labelKey: 'nav.uiKit',
      path: '/ui-kit',
    },
    {
      icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>',
      key: 'more',
      labelKey: 'nav.more',
      // The "More" slot doesn't navigate — it opens the MobileMoreSheet.
      // We pass an empty path so isActive() returns false for it.
      path: '',
    },
  ];

  function isActive(path: string): boolean {
    if (!path) return false;
    // Exact match for '/' (dashboard) — otherwise prefix-match for nested routes
    if (path === '/') return currentRoute === '/' || currentRoute === '';
    return currentRoute === path || currentRoute.startsWith(path + '/');
  }

  function handleClick(slot: (typeof slots)[number]) {
    if (slot.key === 'more') {
      onMoreClick?.();
      return;
    }
    window.location.hash = slot.path === '/' ? '#/' : `#${slot.path}`;
  }

  let lang = $state('en');
  $effect(() => {
    const unsub = currentLang.subscribe((v: string) => (lang = v));
    return unsub;
  });
</script>

<nav class="mbn-root" aria-label="Main navigation">
  {#each slots as slot (slot.key)}
    {@const active = isActive(slot.path)}
    <button
      type="button"
      class="mbn-slot"
      class:mbn-active={active}
      onclick={() => handleClick(slot)}
      aria-current={active ? 'page' : undefined}
      aria-label={t(slot.labelKey, lang)}
      data-nav-key={slot.key}
    >
      <span class="mbn-icon" aria-hidden="true">{@html slot.icon}</span>
      <span class="mbn-label">{t(slot.labelKey, lang)}</span>
    </button>
  {/each}
</nav>

<style>
  /* Mobile-only — hidden at >=768px (md). See Sidebar.svelte for the
     inverse rule that re-enables Sidebar at >=768px. */
  .mbn-root {
    display: flex;
    align-items: stretch;
    justify-content: space-around;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 50;

    /* Glass overlay — matches DESIGN.md §Tooltip/Dropdown/Popover */
    background: color-mix(in srgb, var(--ray-surface) 85%, transparent);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);

    border-top: 1px solid var(--ray-border);
    /* Safe-area: home indicator on iOS, gesture bar on Android. */
    padding-bottom: var(--safe-bottom, 0px);

    /* Min height including safe-area — 56px base + safe-bottom */
    min-height: calc(56px + var(--safe-bottom, 0px));
  }

  /* Above the breakpoint, the desktop sidebar takes over — bottom nav disappears. */
  @media (min-width: 768px) {
    .mbn-root {
      display: none;
    }
  }

  .mbn-slot {
    /* 44×44px minimum tap target (Apple HIG). Width is flex-controlled
       so 6 slots = ~65px each at 390 viewport, which exceeds 44. */
    min-height: 44px;
    min-width: 44px;
    flex: 1 1 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 6px 4px;
    border: none;
    background: transparent;
    color: var(--ray-text-tertiary);
    cursor: pointer;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.25px;
    transition:
      opacity 0.15s ease,
      color 0.15s ease;
    -webkit-tap-highlight-color: transparent;
  }

  .mbn-slot:hover {
    opacity: 0.8;
  }

  .mbn-slot:focus-visible {
    outline: 2px solid var(--ray-blue);
    outline-offset: -2px;
    border-radius: 6px;
  }

  .mbn-active {
    color: var(--ray-text);
    /* Subtle active-state — per Raycast, active item gets a faint bg,
       not a heavy pill. */
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
  }

  .mbn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
  }

  .mbn-icon :global(svg) {
    width: 100%;
    height: 100%;
  }

  .mbn-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
    /* Hide label on very narrow phones (<340px) where 6 labels would
       truncate too aggressively. The icon + aria-label remain visible
       to assistive tech. */
  }
</style>
