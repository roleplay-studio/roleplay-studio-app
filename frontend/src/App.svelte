<script lang="ts">
  import './app.css';
  import { onDestroy, onMount } from 'svelte';

  import { apiBase } from './lib/api';
  import BackendErrorScreen from './lib/BackendErrorScreen.svelte';
  import GlobalDropZone from './lib/GlobalDropZone.svelte';
  import { currentLang, t } from './lib/i18n';
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
  import SplashScreen from './lib/SplashScreen.svelte';
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
  let abortController: AbortController | undefined;
  // Reactive language for the splash screen. Subscribed to currentLang
  // so localized strings update if the user switches language before
  // the backend finishes starting.
  let splashLang = $state('en');
  let unsubLang: (() => void) | undefined;

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

    // React to language changes — the splash strings need to follow
    // the user's choice, not stay frozen in whatever locale was
    // active when onMount ran.
    unsubLang = currentLang.subscribe((v) => (splashLang = v));

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
   * Poll /api/health until the backend reports 200, then check
   * whether first-run setup is needed. While the backend is starting
   * up (listening on the port but the FastAPI lifespan not yet
   * finished) /api/health returns 503 — that's normal during startup,
   * so we keep polling with exponential backoff instead of showing
   * the error screen.
   *
   * Outcomes:
   *   - backendError = undefined, needsSetup = true | false  → ready
   *   - backendError = { kind: 'degraded', status, detail }   → HTTP error
   *   - backendError = { kind: 'unreachable' }                → max attempts
   *
   * `AbortController` lets `onDestroy` cancel an in-flight retry so
   * hot-reload doesn't leave a zombie timer behind. `AbortSignal.
   * timeout` is a safety net against a hung TCP keepalive.
   */
  async function checkBackend() {
    backendError = null;
    needsSetup = null;
    retrying = true;

    const controller = new AbortController();
    abortController = controller;
    let delay = 1000;
    const maxAttempts = 30;

    const sleep = (ms: number) =>
      new Promise<void>((resolve) => setTimeout(resolve, ms));

    // Combine our own controller signal with a 3s safety timeout.
    // ``AbortSignal.any`` was added in Safari 17.4 (macOS 14.4) and
    // the bundle's ``minimumSystemVersion`` is 14.0, so the runtime
    // WebView on older systems throws TypeError instead of returning
    // a usable signal — feature-detect and fall back to our
    // controller-only path. The 3s ceiling is still enforced via a
    // setTimeout below; it just races with the network call instead
    // of being passed through fetch.
    const supportsAny = typeof AbortSignal.any === 'function';
    const makeSignal = (): AbortSignal => {
      if (supportsAny) return AbortSignal.any([controller.signal, AbortSignal.timeout(3000)]);
      const timed = new AbortController();
      const t = setTimeout(() => timed.abort(), 3000);
      // If our outer controller aborts, cancel the timeout so it
      // doesn't leak.
      controller.signal.addEventListener('abort', () => {
        clearTimeout(t);
        timed.abort();
      }, { once: true });
      return timed.signal;
    };

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const res = await fetch(`${apiBase()}/api/health`, {
          cache: 'no-store',
          headers: { Accept: 'application/json' },
          signal: makeSignal(),
        });

        if (res.ok) {
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
          retrying = false;
          return;
        }

        if (res.status === 503) {
          // Backend reachable but lifespan (DB / LLM init) not done yet —
          // keep showing the splash and retry after the current backoff.
          await sleep(delay);
          delay = Math.min(delay * 2, 8000);
          continue;
        }

        // Any other HTTP error → surface to the user.
        let detail: string | undefined;
        try {
          const body = await res.json();
          detail = body?.db_error || body?.detail;
        } catch {
          /* response body wasn't JSON */
        }
        backendError = { detail, kind: 'degraded', status: res.status };
        retrying = false;
        return;
      } catch (e) {
        // AbortError = component destroyed or request timed out.
        // Either way we stop the polling loop quietly.
        if (e instanceof Error && e.name === 'AbortError') {
          retrying = false;
          return;
        }
        // Network failure (DNS, ECONNREFUSED, offline, …) — keep trying.
        await sleep(delay);
        delay = Math.min(delay * 2, 8000);
      }
    }

    // Exhausted retries — give up and surface the error screen.
    retrying = false;
    backendError = { kind: 'unreachable' };
  }

  onDestroy(() => {
    unsubSidebar?.();
    window.removeEventListener('resize', handleResize);
    // Cancel any in-flight health probe + scheduled retry so a hot
    // reload or route away doesn't leave a dangling setTimeout.
    abortController?.abort();
    unsubLang?.();
  });
</script>

{#if backendError !== undefined}
  {#if backendError === null}
    <!-- Backend startup in progress — keep the splash visible until
         /api/health returns 200 (or we exhaust retries). The detail
         line is shown only while we're actively retrying so a stuck
         backend is easy to debug from the screenshot. -->
    <SplashScreen
      title={t('splash.app_name', splashLang)}
      message={t('splash.checking_backend', splashLang)}
      detail={retrying ? `${apiBase()}/api/health` : undefined}
    />
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
  /* Splash-specific styles live in SplashScreen.svelte. App.svelte
     used to draw its own inline spinner here; now that the splash
     is a real component it owns the animation and a11y attributes. */
</style>
