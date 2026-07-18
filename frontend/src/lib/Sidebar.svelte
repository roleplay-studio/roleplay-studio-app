<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import iconUrl from '../icon.png';
  import { currentLang, t } from './i18n';
  import { isMobile, sidebarOpen } from './stores/sidebar';
  import { NavItem } from './ui';

  const { currentRoute = '/' }: { currentRoute?: string } = $props();

  let lang = $state('en');
  let unsubLang: (() => void) | undefined;

  onMount(() => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
  });

  onDestroy(() => {
    unsubLang?.();
  });

  const navKeys: { icon: string; key: string; path: string }[] = [
    { icon: 'bots', key: 'nav.dashboard', path: '/' },
    { icon: 'chat', key: 'nav.chat', path: '/chat' },
    { icon: 'robot', key: 'nav.bots', path: '/bots' },
    { icon: 'users', key: 'nav.personas', path: '/personas' },
    { icon: 'books', key: 'nav.uiKit', path: '/ui-kit' },
    { icon: 'skills', key: 'nav.skills', path: '/skills' },
    { icon: 'settings', key: 'nav.settings', path: '/settings' },
    { icon: 'wizard', key: 'nav.wizard', path: '/setup' },
  ];

  function handleNav(path: string) {
    window.location.hash = path === '/' ? '#/' : `#${path}`;
    if ($isMobile) sidebarOpen.set(false);
  }

  const icons: Record<string, string> = {
    books:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"/><rect x="14" y="2" width="8" height="8" rx="1"/></svg>',
    bots: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/></svg>',
    chat: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"/><path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/></svg>',
    robot:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>',
    settings:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    skills:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/></svg>',
    users:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 21a8 8 0 0 1 10.821-7.487"/><path d="M21.378 16.626a1 1 0 0 0-3.004-3.004l-4.01 4.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z"/><circle cx="10" cy="8" r="5"/></svg>',
    wizard:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/></svg>',
  };
</script>

<aside class="sb-root" class:sb-open={$sidebarOpen} class:sb-closed={!$sidebarOpen}>
  <!-- Brand -->
  <div class="sb-brand">
    <div class="sb-logo">
      <img src={iconUrl} alt="logo" class="sb-logo-img" />
    </div>
    {#if $sidebarOpen}
      <div class="sb-brand-text">
        <h1 class="sb-title">Roleplay Studio</h1>
        <p class="sb-subtitle">{t('app.subtitle', lang)}</p>
      </div>
      <button class="sb-collapse-btn" onclick={() => sidebarOpen.set(false)}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg
        >
      </button>
    {:else}
      <button class="sb-expand-btn" onclick={() => sidebarOpen.set(true)}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg
        >
      </button>
    {/if}
  </div>

  <!-- Navigation -->
  <nav class="sb-nav">
    {#each navKeys as r (r.path)}
      {@const isActive = currentRoute === r.path}
      <NavItem
        icon={icons[r.icon]}
        label={t(r.key, lang)}
        active={isActive}
        collapsed={!$sidebarOpen}
        onclick={() => handleNav(r.path)}
      />
    {/each}
  </nav>

  <!-- Footer -->
  {#if $sidebarOpen}
    <div class="sb-footer">
      <span class="sb-version">v0.1.0</span>
    </div>
  {/if}
</aside>

<style>
  /* ─── Theme Variables (fallbacks for non-Raycast pages) ─── */
  :root {
    --sb-bg: #f5f5f7;
    --sb-border: rgba(0, 0, 0, 0.06);
    --sb-text: #1d1d1f;
    --sb-text-secondary: #6e6e73;
    --sb-text-dim: #aeaeb2;
    --sb-hover: rgba(0, 0, 0, 0.04);
    --sb-active-bg: rgba(0, 0, 0, 0.06);
    --sb-active-text: #1d1d1f;
    --sb-logo-bg: #1d1d1f;
    --sb-logo-text: #ffffff;
  }
  :root.dark {
    --sb-bg: #101111;
    --sb-border: rgba(255, 255, 255, 0.06);
    --sb-text: #f9f9f9;
    --sb-text-secondary: #9c9c9d;
    --sb-text-dim: #434345;
    --sb-hover: rgba(255, 255, 255, 0.04);
    --sb-active-bg: rgba(255, 255, 255, 0.06);
    --sb-active-text: #f9f9f9;
    --sb-logo-bg: #f9f9f9;
    --sb-logo-text: #07080a;
  }

  .sb-root {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 40;
    height: 100vh;
    background: var(--sb-bg);
    border-right: 1px solid var(--sb-border);
    display: flex;
    flex-direction: column;
    transition: width 0.25s ease;
    overflow: hidden;
  }
  .sb-open {
    width: 220px;
  }
  .sb-closed {
    width: 60px;
  }

  /* ─── Brand ─── */
  .sb-brand {
    display: flex;
    align-items: center;
    height: 56px;
    padding: 0 14px;
    border-bottom: 1px solid var(--sb-border);
    flex-shrink: 0;
    gap: 10px;
  }
  .sb-logo {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    /*background: var(--sb-logo-bg);*/
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    overflow: hidden;
    transition: opacity 0.15s ease;
  }
  .sb-logo-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .sb-brand-text {
    flex: 1;
    min-width: 0;
  }
  .sb-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--sb-text);
    letter-spacing: 0.2px;
    margin: 0;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sb-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 400;
    color: var(--sb-text-dim);
    letter-spacing: 0.2px;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sb-collapse-btn,
  .sb-expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    /* Phase 4.2 — Apple HIG / Material 3 minimum tap target is 44×44px.
       Visible icon stays 24px but the button is padded to a 44×44 hit
       area so the user can hit it on tablet touchscreens without
       zooming in. */
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 6px;
    /*background: transparent;*/
    color: var(--sb-text-dim);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.12s ease;
  }
  .sb-collapse-btn:hover,
  .sb-expand-btn:hover {
    /*background: var(--sb-hover);*/
    color: var(--sb-text);
  }
  .sb-expand-btn {
    position: absolute;
    right: 14px;
    top: 13px;
    opacity: 0;
    transition: opacity 0.15s ease;
    background: var(--sb-bg);
    border: 1px solid var(--sb-border);
    border-radius: 6px;
    /* Phase 4.2 — 44×44 tap target (overrides base 44×44 width/height
       above only by inheriting them; we keep the override here to
       document intent) */
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  }
  .sb-closed .sb-brand:hover .sb-expand-btn {
    opacity: 1;
  }

  .sb-closed .sb-brand:hover .sb-logo {
    opacity: 0;
  }

  /* ─── Navigation ─── */
  .sb-nav {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  /* ─── Footer ─── */
  .sb-footer {
    padding: 10px;
    border-top: 1px solid var(--sb-border);
    text-align: center;
    flex-shrink: 0;
  }
  .sb-version {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 400;
    color: var(--sb-text-dim);
    letter-spacing: 0.2px;
  }
</style>
