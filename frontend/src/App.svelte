<script lang="ts">
  import './app.css';
  import { onDestroy, onMount } from 'svelte';

  import { apiBase } from './lib/api';
  import BackendErrorScreen from './lib/BackendErrorScreen.svelte';
  import GlobalDropZone from './lib/GlobalDropZone.svelte';
  import { currentLang, t } from './lib/i18n';
  import MobileBottomNav from './lib/MobileBottomNav.svelte';
  import MobileMoreSheet from './lib/MobileMoreSheet.svelte';
  import OfflineBanner from './lib/OfflineBanner.svelte';
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
  import SkillsLibraryPage from './lib/pages/SkillsLibraryPage.svelte';
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
  // MobileMoreSheet visibility — toggled by MobileBottomNav's "More" slot.
  let moreSheetOpen = $state(false);

  /**
   * Viewport tier:
   *   - 'phone'  (< 768px)  — Sidebar hidden, MobileBottomNav visible
   *   - 'tablet' (768-1023) — Sidebar visible (collapsed icon-only via CSS),
   *                          no bottom-nav
   *   - 'desktop' (>= 1024) — Sidebar visible (full, user-toggleable)
   *
   * isMobile from sidebar.ts store means "< 1024px" — we keep that
   * for legacy reasons but introduce the finer-grained tier here.
   * isPhone is what gates bottom-nav visibility.
   */
  let viewportTier = $state<'desktop' | 'phone' | 'tablet'>('desktop');

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
    const w = window.innerWidth;
    const mobile = w < 1024;
    const phone = w < 768;
    isMobile.set(mobile);
    viewportTier = phone ? 'phone' : mobile ? 'tablet' : 'desktop';
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
   * Phase 4.4 — keep `<meta name="theme-color">` in sync with the
   * resolved theme. The HTML already declares both light and dark
   * defaults in index.html, but if the user toggles light/dark/system
   * at runtime the meta tag still shows the boot-time color. We watch
   * the `<html>` class for the `.dark` class added by theme.ts and
   * swap the meta tag accordingly.
   *
   * Safari iOS and Android Chrome use this color for the status bar
   * and address bar tint, so a stale value is visually jarring when
   * the user toggles themes.
   */
  $effect(() => {
    if (typeof document === 'undefined') return;

    const apply = () => {
      const isDark = document.documentElement.classList.contains('dark');
      const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
      if (!meta) return;
      // Same hex values as DESIGN.md §Colors / index.html defaults.
      meta.setAttribute('content', isDark ? '#07080a' : '#f5f5f7');
    };

    apply();

    // Watch for class changes on <html> (added/removed by theme.ts).
    const observer = new MutationObserver(apply);
    observer.observe(document.documentElement, {
      attributeFilter: ['class'],
      attributes: true,
    });

    return () => observer.disconnect();
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

    const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

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
      controller.signal.addEventListener(
        'abort',
        () => {
          clearTimeout(t);
          timed.abort();
        },
        { once: true },
      );
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
  <div class="app-shell" data-tier={viewportTier}>
    {#if $sidebarOpen && $isMobile && viewportTier === 'tablet'}
      <!-- Tablet backdrop (only when sidebar is open on tablet — phone
           doesn't have a sidebar at all, so no backdrop needed) -->
      <div
        class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm transition-opacity"
        onclick={() => sidebarOpen.set(false)}
      ></div>
    {/if}

    {#if viewportTier !== 'phone'}
      <Sidebar {currentRoute} />
    {/if}

    <main class="app-main" class:sidebar-open={$sidebarOpen && viewportTier === 'desktop'}>
      <div class="w-full relative">
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
        {:else if baseRoute === '/skills'}
          <SkillsLibraryPage />
        {:else if baseRoute === '/ui-kit'}
          <UIPreview />
        {:else if baseRoute === '/setup'}
          <SetupWizard />
        {:else if baseRoute === '/settings'}
          <SettingsPage />
        {/if}
      </div>
    </main>

    {#if viewportTier === 'phone'}
      <MobileBottomNav {currentRoute} onMoreClick={() => (moreSheetOpen = true)} />
      <MobileMoreSheet open={moreSheetOpen} onclose={() => (moreSheetOpen = false)} />
    {/if}
  </div>
  <GlobalDropZone />
  <!-- Phase 5.4 — OfflineBanner is rendered outside the main shell so it
       sits above any page content, at z-index 70 (above BottomNav's 50,
       above MobileMoreSheet's 61). It only renders when navigator.onLine
       becomes false. -->
  <OfflineBanner />
{/if}

<style>
  /* Splash-specific styles live in SplashScreen.svelte. App.svelte
     used to draw its own inline spinner here; now that the splash
     is a real component it owns the animation and a11y attributes. */

  /* ── App shell — Phase 1.5 / 1.6 (MOBILE_PLAN.md) ──────────── */
  /*
    Previously the shell used `class="flex min-h-screen h-screen ..."`
    and the <main> used `class:md:ml-[220px]={$sidebarOpen}`. That
    broke mobile: the Sidebar was always in the DOM at full width
    and the main content was squeezed into ~200px on a 390 viewport.

    New model:
      - phone  (<768): full-width main, bottom-nav reserved space
      - tablet (768-1023): main has 220px (sidebar open) or 60px (closed) on left
      - desktop (>=1024): same as tablet but user-toggleable
  */
  .app-shell {
    display: flex;
    min-height: 100vh;
    height: 100vh;
    background: var(--ray-bg);
    color: var(--ray-text);
    overflow: hidden;
  }

  .app-main {
    flex: 1 1 0;
    width: 100%;
    overflow-y: auto;
    min-height: 0;
    /* Default: 0 left margin (phone), then 60px (sidebar collapsed on tablet/desktop) */
    margin-left: 0;
    transition: margin-left 0.25s ease;
    /* Reserve bottom-nav height on phone so content doesn't go under it.
       MobileBottomNav height = 56px + safe-area-inset-bottom. */
    padding-bottom: 0;
  }

  /* Tablet+ (>=768): main shifts right to accommodate Sidebar */
  @media (min-width: 768px) {
    .app-main {
      margin-left: 60px;
    }
    /* When sidebar is open AND desktop (>=1024), push main further */
    @media (min-width: 1024px) {
      .app-main.sidebar-open {
        margin-left: 220px;
      }
    }
  }

  /* Phone (<768): reserve bottom-nav space */
  @media (max-width: 767.98px) {
    .app-main {
      padding-bottom: calc(56px + var(--safe-bottom, 0px));
    }
  }
</style>
