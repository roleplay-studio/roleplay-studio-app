<script lang="ts">
  import { thumbUrl } from './api';
  import { getAutoplayTts, onChatSettingsChange, setAutoplayTts } from './chatSettings';
  import { t } from './i18n';
  import { GeneratedAvatar, Toggle } from './ui';

  function formatTokens(n: number): string {
    if (n >= 1000) {
      const k = (n / 1000).toFixed(1);
      return k.endsWith('.0') ? `${Math.round(n / 1000)}k` : `${k}k`;
    }
    return String(n);
  }

  const {
    botAvatarPath = null as null | string,
    botName = '',
    compressing = false,
    hasSummary = false,
    lang = 'en',
    messageCount = 0,
    onbotClick,
    oncompress,
    ondeleteThread,
    oneditbot,
    onexport,
    onnewthread,
    ontoggleThreads,
    totalTokens = 0,
  }: {
    botAvatarPath?: null | string;
    botName?: string;
    compressing?: boolean;
    hasSummary?: boolean;
    lang?: string;
    messageCount?: number;
    onbotClick?: () => void;
    oncompress?: () => void;
    ondeleteThread?: () => void;
    oneditbot?: () => void;
    onexport?: () => void;
    onnewthread?: () => void;
    ontoggleThreads?: () => void;
    totalTokens?: number;
  } = $props();

  // Dropdown state — single shared menu for thread actions.
  let menuOpen = $state(false);
  let menuRoot: HTMLDivElement | undefined = $state();
  // Settings popover (gear icon). Independent state from `menuOpen`
  // so both popovers can never be open at once — closing one when
  // the other opens avoids two stacked dropdowns fighting for focus.
  let settingsOpen = $state(false);
  let settingsRoot: HTMLDivElement | undefined = $state();
  // Reactive mirror of the chat-settings store. ``onChatSettingsChange``
  // fires once on subscribe with the current value, so this also
  // covers the initial render after a page reload.
  let autoplayTts = $state(getAutoplayTts());
  $effect(() => onChatSettingsChange((s) => (autoplayTts = s.autoplayTts)));

  function toggleMenu() {
    menuOpen = !menuOpen;
    if (menuOpen) settingsOpen = false;
  }
  function closeMenu() {
    menuOpen = false;
  }
  function toggleSettings() {
    settingsOpen = !settingsOpen;
    if (settingsOpen) menuOpen = false;
  }
  function closeSettings() {
    settingsOpen = false;
  }

  // Click-outside + Escape close — covers both popovers. ``menuOpen``
  // and ``settingsOpen`` are mutually exclusive (openers close the
  // other), so a single document listener handles them together.
  $effect(() => {
    if (!menuOpen && !settingsOpen) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (menuOpen && menuRoot && !menuRoot.contains(target)) closeMenu();
      if (settingsOpen && settingsRoot && !settingsRoot.contains(target)) closeSettings();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        closeMenu();
        closeSettings();
      }
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  });

  function runAndClose(fn?: () => void) {
    return () => {
      closeMenu();
      fn?.();
    };
  }
</script>

<header class="ch-header">
  <button onclick={onbotClick} class="ch-bot">
    {#if botAvatarPath}
      <img src={thumbUrl(botAvatarPath, 50)} alt={botName} class="ch-avatar" />
    {:else}
      <GeneratedAvatar name={botName} size={36} />
    {/if}
    <div class="ch-info">
      <p class="ch-name">{botName}</p>
      <p class="ch-stats">
        {t('chat.stats', lang)
          .replace('{msgs}', String(messageCount))
          .replace('{tokens}', formatTokens(totalTokens))}
      </p>
    </div>
  </button>

  <div class="ch-actions">
    <button class="ch-btn" onclick={ontoggleThreads} title={t('thread.title', lang)}>
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-history-icon lucide-history"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>
    </button>

    <div class="ch-menu-root" bind:this={settingsRoot}>
      <button
        class="ch-btn"
        class:active={settingsOpen}
        onclick={toggleSettings}
        title={t('chat.settings', lang)}
        aria-haspopup="true"
        aria-expanded={settingsOpen}
      >
        <!-- Gear icon. Same footprint as the other ``ch-btn`` glyphs. -->
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          ><path
            d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
          ></path><circle cx="12" cy="12" r="3"></circle></svg
        >
      </button>
      {#if settingsOpen}
        <div class="ch-settings" role="dialog" aria-label={t('chat.settings_title', lang)}>
          <div class="ch-settings-title">{t('chat.settings_title', lang)}</div>
          <!--
            Each ``ch-settings-row`` is one toggle. Add more rows here
            as new chat-window settings come online (e.g. "send on
            Enter", "collapse greetings on switch"). Helper text below
            explains the effect; the row itself uses the shared
            Toggle component for visual consistency with SettingsPage.
          -->
          <div class="ch-settings-row">
            <div class="ch-settings-row-text">
              <span class="ch-settings-label">{t('chat.autoplay_tts_label', lang)}</span>
              <span class="ch-settings-help">{t('chat.autoplay_tts_help', lang)}</span>
            </div>
            <Toggle
              checked={autoplayTts}
              onchange={(e) => {
                const next = (e.currentTarget as HTMLInputElement).checked;
                setAutoplayTts(next);
              }}
            />
          </div>
        </div>
      {/if}
    </div>

    <div class="ch-menu-root" bind:this={menuRoot}>
      <button
        class="ch-btn"
        class:active={menuOpen || hasSummary}
        onclick={toggleMenu}
        title={t('chat.menu', lang)}
        aria-haspopup="true"
        aria-expanded={menuOpen}
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
          ><circle cx="12" cy="5" r="1.5" fill="currentColor"></circle><circle
            cx="12"
            cy="12"
            r="1.5"
            fill="currentColor"
          ></circle><circle cx="12" cy="19" r="1.5" fill="currentColor"></circle></svg
        >
      </button>
      {#if menuOpen}
        <div class="ch-menu" role="menu">
          <button class="ch-menu-item" role="menuitem" onclick={runAndClose(onnewthread)}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"
              ></line></svg
            >
            <span>{t('chat.new_thread', lang)}</span>
          </button>
          <button
            class="ch-menu-item"
            role="menuitem"
            disabled={compressing}
            onclick={runAndClose(oncompress)}
          >
            {#if compressing}
              <span class="ch-spinner ch-spinner-sm"></span>
            {:else}
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                ><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path
                  d="M2 12l10 5 10-5"
                ></path></svg
              >
            {/if}
            <span
              >{hasSummary
                ? t('chat.summary_active', lang)
                : t('chat.summarize_thread', lang)}</span
            >
          </button>
          <button class="ch-menu-item" role="menuitem" onclick={runAndClose(onexport)}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline
                points="7 10 12 15 17 10"
              ></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg
            >
            <span>{t('chat.export', lang)}</span>
          </button>
          <button class="ch-menu-item" role="menuitem" onclick={runAndClose(oneditbot)}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M12 20h9"></path><path
                d="M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4 12.5-12.5z"
              ></path></svg
            >
            <span>{t('chat.edit_bot', lang)}</span>
          </button>
          <div class="ch-menu-divider"></div>
          <button
            class="ch-menu-item ch-menu-danger"
            role="menuitem"
            onclick={runAndClose(ondeleteThread)}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><polyline points="3 6 5 6 21 6"></polyline><path
                d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
              ></path></svg
            >
            <span>{t('chat.delete_thread', lang)}</span>
          </button>
        </div>
      {/if}
    </div>
  </div>
</header>

<style>
  :root {
    --ch-bg: #ffffff;
    --ch-border: rgba(0, 0, 0, 0.06);
    --ch-text: #1d1d1f;
    --ch-text-secondary: #6e6e73;
    --ch-text-tertiary: #86868b;
    --ch-hover: rgba(0, 0, 0, 0.04);
    --ch-red: #ff3b30;
    --ch-green: #34c759;
  }
  :root.dark {
    --ch-bg: #101111;
    --ch-border: rgba(255, 255, 255, 0.06);
    --ch-text: #f9f9f9;
    --ch-text-secondary: #9c9c9d;
    --ch-text-tertiary: #6a6b6c;
    --ch-hover: rgba(255, 255, 255, 0.04);
    --ch-red: #ff6363;
    --ch-green: #5fc992;
  }

  .ch-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 20px;
    border-bottom: 1px solid var(--ch-border);
    background: var(--ch-bg);
    flex-shrink: 0;
  }
  .ch-bot {
    display: flex;
    align-items: center;
    gap: 10px;
    border: none;
    background: none;
    cursor: pointer;
    transition: opacity 0.12s ease;
    text-align: left;
    padding: 0;
  }
  .ch-bot:hover {
    opacity: 0.75;
  }
  .ch-avatar {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
  }
  .ch-name {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--ch-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .ch-stats {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--ch-text-tertiary);
    margin: 2px 0 0;
    letter-spacing: 0.2px;
  }

  .ch-actions {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .ch-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    /* Phase 4.2 — 44×44px tap target per Apple HIG / Material 3.
       The header can comfortably fit 6 of these on a 390 viewport
       (each gets ~65px), so we don't need to shrink the visible icon. */
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ch-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
    flex-shrink: 0;
  }
  .ch-btn:hover {
    background: var(--ch-hover);
    color: var(--ch-text);
  }
  .ch-btn.active {
    color: var(--ch-green);
  }
  .ch-btn.danger:hover {
    background: color-mix(in srgb, var(--ch-red) 10%, transparent);
    color: var(--ch-red);
  }
  .ch-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .ch-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid color-mix(in srgb, var(--ch-text) 20%, transparent);
    border-top-color: var(--ch-text);
    border-radius: 50%;
    animation: ch-spin 0.6s linear infinite;
  }
  @keyframes ch-spin {
    to {
      transform: rotate(360deg);
    }
  }
  .ch-divider {
    width: 1px;
    height: 20px;
    background: var(--ch-border);
    margin: 0 4px;
  }
  .ch-menu-root {
    position: relative;
    display: inline-flex;
  }
  .ch-menu {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 200px;
    padding: 4px;
    background: var(--ch-bg);
    border: 1px solid var(--ch-border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .ch-menu-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border: none;
    background: transparent;
    color: var(--ch-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s ease;
    white-space: nowrap;
  }
  .ch-menu-item:hover:not(:disabled) {
    background: var(--ch-hover);
  }
  .ch-menu-item:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .ch-menu-danger {
    color: var(--ch-red);
  }
  .ch-menu-danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ch-red) 12%, transparent);
  }
  .ch-menu-divider {
    height: 1px;
    background: var(--ch-border);
    margin: 4px 2px;
  }
  .ch-spinner-sm {
    width: 14px;
    height: 14px;
    border-width: 2px;
  }

  /* Settings popover. Reuses the same visual shell as ``ch-menu`` so
     the two popovers feel like siblings, with extra width for a
     label+help+toggle row. Extend ``.ch-settings-row`` blocks when new
     toggles land — no extra layout work needed. */
  .ch-settings {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 280px;
    padding: 6px;
    background: var(--ch-bg);
    border: 1px solid var(--ch-border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ch-settings-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    color: var(--ch-text-tertiary);
    padding: 4px 8px 2px;
  }
  .ch-settings-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px;
    border-radius: 6px;
  }
  .ch-settings-row:hover {
    background: var(--ch-hover);
  }
  .ch-settings-row-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
  }
  .ch-settings-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--ch-text);
    letter-spacing: 0.2px;
  }
  .ch-settings-help {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ch-text-tertiary);
    line-height: 1.4;
    letter-spacing: 0.1px;
  }
</style>
