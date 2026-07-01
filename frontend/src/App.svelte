<script lang="ts">
  import './app.css';
  import { onDestroy, onMount } from 'svelte';

  import { apiBase } from './lib/api';
  import BackendErrorScreen from './lib/BackendErrorScreen.svelte';
  import GlobalDropZone from './lib/GlobalDropZone.svelte';
  import { currentLang } from './lib/i18n';
  import BotCreatePage from './lib/pages/BotCreatePage.svelte';
  import BotEditPage from './lib/pages/BotEditPage.svelte';
  import BotPreviewPage from './lib/pages/BotPreviewPage.svelte';
  import BotsPage from './lib/pages/BotsPage.svelte';
  import Chat from './lib/pages/Chat.svelte';
  import ConnectToServer from './lib/pages/ConnectToServer.svelte';
  import Dashboard from './lib/pages/Dashboard.svelte';
  import PersonasPage from './lib/pages/PersonasPage.svelte';
  import SettingsPage from './lib/pages/SettingsPage.svelte';
  import SetupWizard from './lib/pages/SetupWizard.svelte';
  import Sidebar from './lib/Sidebar.svelte';
  import { isMobile, sidebarOpen } from './lib/stores/sidebar';
  import { applyThemePreference, initTheme } from './lib/theme';
  import UIPreview from './lib/ui/_catalog/UIPreview.svelte';

  let currentRoute = $state('/');
  let queryParams = $state<Record<string, string>>({});
  let routePath = $state('');
  let needsSetup = $state<boolean | null>(null);
  // null = checking, object = backend is down, undefined = healthy
  let backendError = $state<
    null | undefined | { detail?: string; kind: 'degraded' | 'unreachable'; status?: number }
  >(null);
  let retrying = $state(false);
  let unsubSidebar: (() => void) | undefined;

  function parseHash() {
    const hash = window.location.hash.slice(1) || '/';
    const normalized = '/' + hash.replace(/^\/+/, '').split('/').filter(Boolean).join('/');
    const [path, qs] = normalized.split('?');
    routePath = path;
    currentRoute = path;
    queryParams = {};
    if (qs) {
      for (const part of qs.split('&')) {
        const [k, v] = part.split('=');
        queryParams[decodeURIComponent(k)] = decodeURIComponent(v || '');
      }
    }
  }

  const baseRoute = $derived(
    routePath.startsWith('/bots/')
      ? '/bots'
      : routePath.startsWith('/bot/')
        ? '/bot'
        : currentRoute,
  );

  const botEditId = $derived(
    routePath.startsWith('/bots/') ? routePath.slice(6) : queryParams.id || '0',
  );

  const botPreviewId = $derived(routePath.startsWith('/bot/') ? routePath.slice(5) : '0');

  const SIDEBAR_STORAGE_KEY = 'sidebar_open';

  function loadSidebarPreference(): boolean {
    try {
      const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (saved !== null) return saved === 'true';
    } catch {
      /* ignore */
    }
    return true;
  }

  function saveSidebarPreference(open: boolean) {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, open ? 'true' : 'false');
    } catch {
      /* ignore */
    }
  }

  function handleResize() {
    const mobile = window.innerWidth < 1024;
    isMobile.set(mobile);
    if (mobile) {
      sidebarOpen.set(false);
    } else {
      const saved = loadSidebarPreference();
      sidebarOpen.set(saved);
    }
  }

  function setupSidebarPersistence() {
    // Persist sidebar state to localStorage whenever it changes
    // Ignore saves when the window is below desktop breakpoint
    return sidebarOpen.subscribe((open) => {
      if (window.innerWidth < 1024) return; // don't save forced-closed state on mobile
      saveSidebarPreference(open);
    });
  }

  onMount(async () => {
    parseHash();
    window.addEventListener('hashchange', parseHash);
    window.addEventListener('resize', handleResize);
    handleResize();

    // Restore sidebar preference from localStorage (desktop only)
    if (window.innerWidth >= 1024) {
      sidebarOpen.set(loadSidebarPreference());
    }

    // Persist sidebar state on changes
    unsubSidebar = setupSidebarPersistence();

    // Initialize theme from localStorage (instant)
    const localPref = initTheme();

    // Load config from server (language + theme fallback) — best-effort,
    // a missing backend here is not fatal: the health check below will
    // surface a proper error if it's actually down.
    try {
      const res = await fetch(`${apiBase()}/api/config`);
      const data = await res.json();
      if (data.language) currentLang.set(data.language);
      // If no stored preference, use server's theme
      if (localPref === 'system' && data.theme && data.theme !== 'system') {
        applyThemePreference(data.theme);
      }
    } catch {
      /* ignore — the health check below will explain */
    }

    await checkBackend();
  });

  /**
   * Hit /api/health and translate the result into one of three states:
   *   - backendError = {kind: 'unreachable'} — network error, server is down
   *   - backendError = {kind: 'degraded', status, detail} — 503 from health
   *   - backendError = undefined, needsSetup = true | false — normal path
   */
  async function checkBackend() {
    retrying = true;
    try {
      const res = await fetch(`${apiBase()}/api/health`, {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (res.status === 200) {
        backendError = undefined;
        // Backend is healthy — now check whether first-run setup is needed.
        try {
          const statusRes = await fetch(`${apiBase()}/api/setup/status`);
          const data = await statusRes.json();
          needsSetup = !!data.needs_setup;
        } catch {
          // Health says ok but setup status is broken — fall back to wizard
          // so the user at least sees a working UI.
          needsSetup = true;
        }
        return;
      }
      if (res.status === 503) {
        // Backend reachable but degraded. Try to extract the db_error
        // so the user sees something actionable.
        let detail: string | undefined;
        try {
          const body = await res.json();
          detail = body?.db_error || body?.detail;
        } catch {
          /* response body wasn't JSON */
        }
        backendError = { detail, kind: 'degraded', status: 503 };
        return;
      }
      // Some other HTTP error — treat as unreachable from the user's POV.
      backendError = { kind: 'unreachable', status: res.status };
    } catch (e) {
      // Network failure (DNS, ECONNREFUSED, offline, …).
      const msg = e instanceof Error ? e.message : String(e);
      backendError = { detail: msg, kind: 'unreachable' };
    } finally {
      retrying = false;
    }
  }

  onDestroy(() => {
    unsubSidebar?.();
    window.removeEventListener('resize', handleResize);
  });
</script>

{#if backendError !== undefined}
  {#if backendError === null}
    <!-- Initial health check in flight — keep the page neutral so we
         don't flash the main app before we know if the backend is up. -->
    <div class="boot-loading">
      <div class="boot-spinner"></div>
    </div>
  {:else}
    <BackendErrorScreen
      kind={backendError.kind}
      status={backendError.status}
      detail={backendError.detail}
      apiBase={apiBase()}
      onretry={checkBackend}
      {retrying}
    />
  {/if}
{:else if needsSetup}
  <SetupWizard />
{:else}
  <div class="flex min-h-screen bg-theme text-theme">
    {#if $sidebarOpen && $isMobile}
      <!-- Mobile backdrop -->
      <div
        class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm transition-opacity"
        onclick={() => sidebarOpen.set(false)}
      ></div>
    {/if}

    <Sidebar {currentRoute} />

    <main
      class="flex-1 w-full overflow-hidden transition-all duration-300 ml-15"
      class:md:ml-[220px]={$sidebarOpen}
    >
      <div class="w-full relative">
        <!-- {#if !$sidebarOpen}
          <button
            onclick={() => sidebarOpen.set(true)}
            class="absolute top-7 left-0 z-10 w-8 h-8 flex items-center justify-center rounded-lg bg-theme-surface/80 backdrop-blur-lg border border-theme text-theme-secondary hover:text-theme shadow-sm transition-all hover:bg-theme-surface"
            aria-label="Open sidebar"
          >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-5">
                <path fill-rule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
              </svg>

          </button>
        {/if} -->
        {#if baseRoute === '/connect'}
          <ConnectToServer />
        {:else if baseRoute === '/' && routePath === '/'}
          <Dashboard />
        {:else if baseRoute === '/bot'}
          <BotPreviewPage botId={botPreviewId} />
        {:else if baseRoute === '/chat'}
          <Chat
            botId={queryParams.bot || '0'}
            personaId={queryParams.persona || null}
            threadId={queryParams.thread || null}
          />
        {:else if baseRoute === '/bots' && botEditId === 'create'}
          <BotCreatePage />
        {:else if baseRoute === '/bots' && botEditId !== '0'}
          <BotEditPage botId={botEditId} />
        {:else if baseRoute === '/bots'}
          <BotsPage />
        {:else if baseRoute === '/personas'}
          <PersonasPage />
        {:else if baseRoute === '/ui-kit'}
          <UIPreview />
        {:else if baseRoute === '/setup'}
          <SetupWizard />
        {:else if baseRoute === '/settings'}
          <SettingsPage />
        {/if}
      </div>
    </main>
  </div>
  <GlobalDropZone />
{/if}

<style>
  .boot-loading {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--ray-bg);
    z-index: 9999;
  }
  .boot-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--ray-border-strong);
    border-top-color: var(--ray-accent);
    border-radius: 50%;
    animation: boot-spin 0.7s linear infinite;
  }
  @keyframes boot-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
