<script lang="ts">
  import { getServerInfo, type ServerInfo } from '../api';
  import { t } from '../i18n';

  /**
   * Connect to Server screen — shown on first launch (no URL saved)
   * or when the user navigates to /connect manually. In Tauri Android
   * this is the entry point; in web/dev it's bypassed.
   */

  let url = $state(localStorage.getItem('serverUrl') ?? '');
  let testing = $state(false);
  let saving = $state(false);
  let scanning = $state(false);
  let lastTest = $state<null | ServerInfo>(null);
  let error = $state<null | string>(null);

  /** Strip trailing slashes; require http(s):// scheme. */
  function normalizeUrl(raw: string): string {
    return raw.trim().replace(/\/+$/, '');
  }

  const urlLooksValid = $derived(/^https?:\/\/[^\s]+/i.test(url.trim()));
  const isInsecure = $derived(/^http:\/\//i.test(url.trim()));
  const canTest = $derived(urlLooksValid && !testing);

  async function testConnection() {
    if (!canTest) return;
    testing = true;
    error = null;
    try {
      lastTest = await getServerInfo(normalizeUrl(url));
    } catch (e) {
      lastTest = null;
      const msg = e instanceof Error ? e.message : String(e);
      error = msg.includes('Failed to fetch')
        ? t('connect.http_unreachable', $lang)
        : t('connect.test_failed', $lang).replace('{detail}', msg);
    } finally {
      testing = false;
    }
  }

  function save() {
    saving = true;
    try {
      localStorage.setItem('serverUrl', normalizeUrl(url));
      // Notify other parts of the app
      window.dispatchEvent(new CustomEvent('serverurl-changed'));
      // Navigate to the main app
      window.location.hash = '/';
    } finally {
      saving = false;
    }
  }

  function skip() {
    // Use dev default — don't persist anything
    window.location.hash = '/';
  }

  function reset() {
    if (!confirm($lang === 'ru' ? 'Удалить сохранённый URL сервера?' : 'Clear saved server URL?')) {
      return;
    }
    localStorage.removeItem('serverUrl');
    url = '';
    lastTest = null;
    error = null;
    window.location.hash = '/connect';
  }

  /**
   * QR scan entry point. In Tauri Android this calls the Rust
   * `scan_qr` command which opens the camera. In web/dev it shows
   * a prompt as a fallback (no real camera).
   */
  async function scanQr() {
    scanning = true;
    error = null;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tauri = (window as any).__TAURI__;
      if (tauri?.core?.invoke) {
        const scanned: string = await tauri.core.invoke('scan_qr');
        handleScannedText(scanned);
      } else {
        // Dev/web fallback — prompt the user
        const scanned = prompt(
          $lang === 'ru'
            ? 'Введи URL (dev-режим, камера недоступна):'
            : 'Enter URL (dev mode, no camera):',
        );
        if (scanned) handleScannedText(scanned);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('permission') || msg.includes('denied')) {
        error = t('connect.qr_camera_denied', $lang);
      } else {
        error = t('connect.test_failed', $lang).replace('{detail}', msg);
      }
    } finally {
      scanning = false;
    }
  }

  function handleScannedText(scanned: string) {
    // URL may include #token fragment in the future
    const [pureUrl] = scanned.split('#');
    if (!/^https?:\/\/[^\s]+/i.test(pureUrl)) {
      error = t('connect.qr_invalid_format', $lang);
      return;
    }
    url = pureUrl;
    error = null;
    // Auto-test after a successful scan
    testConnection();
  }

  // Reactive: use the i18n current language
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lang = (window as any).__i18n_lang__ ?? 'en';
</script>

<div class="connect-page">
  <div class="connect-card">
    <h1 class="connect-title">{t('connect.title', $lang)}</h1>
    <p class="connect-subtitle">{t('connect.subtitle', $lang)}</p>

    <label class="connect-label" for="server-url">
      {t('connect.url_label', $lang)}
    </label>
    <input
      id="server-url"
      type="url"
      class="connect-input"
      bind:value={url}
      placeholder={t('connect.url_placeholder', $lang)}
      autocomplete="off"
      spellcheck="false"
    />

    {#if isInsecure}
      <p class="connect-warn">{t('connect.insecure_warning', $lang)}</p>
    {/if}

    <div class="connect-actions">
      <button type="button" class="ray-btn" onclick={scanQr} disabled={scanning}>
        {scanning ? t('connect.scanning', $lang) : t('connect.scan_qr', $lang)}
      </button>

      <button type="button" class="ray-btn" onclick={testConnection} disabled={!canTest}>
        {testing ? t('connect.testing', $lang) : t('connect.test_connection', $lang)}
      </button>
    </div>

    {#if lastTest}
      <p class="connect-ok">
        ✓ {t('connect.test_ok', $lang)} (v{lastTest.version})
      </p>
    {/if}

    {#if error}
      <p class="connect-err">{error}</p>
    {/if}

    <div class="connect-actions connect-actions-bottom">
      <button
        type="button"
        class="ray-btn primary"
        onclick={save}
        disabled={!urlLooksValid || saving}
      >
        {t('connect.save', $lang)}
      </button>
      <button type="button" class="ray-btn ghost" onclick={skip}>
        {t('connect.skip', $lang)}
      </button>
    </div>

    {#if localStorage.getItem('serverUrl')}
      <button type="button" class="connect-reset" onclick={reset}>
        {t('connect.reset', $lang)}
      </button>
    {/if}
  </div>
</div>

<style scoped>
  .connect-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px 16px;
    background: var(--ray-bg, #07080a);
  }

  .connect-card {
    width: 100%;
    max-width: 440px;
    padding: 32px 28px;
    background: var(--ray-card-bg, rgba(255, 255, 255, 0.03));
    border: 1px solid var(--ray-border, #2e2f30);
    border-radius: 14px;
    box-shadow:
      0 1px 0 rgba(255, 255, 255, 0.04) inset,
      0 12px 32px rgba(0, 0, 0, 0.4);
  }

  .connect-title {
    margin: 0 0 8px 0;
    font-size: 22px;
    font-weight: 600;
    color: var(--ray-text, #f0f1f2);
    letter-spacing: -0.01em;
  }

  .connect-subtitle {
    margin: 0 0 24px 0;
    font-size: 14px;
    line-height: 1.5;
    color: var(--ray-text-dim, #8a8d92);
  }

  .connect-label {
    display: block;
    margin-bottom: 6px;
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-dim, #8a8d92);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .connect-input {
    width: 100%;
    box-sizing: border-box;
    padding: 11px 14px;
    font-size: 15px;
    font-family: var(--ray-font-mono, monospace);
    color: var(--ray-text, #f0f1f2);
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid var(--ray-border, #2e2f30);
    border-radius: 8px;
    outline: none;
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
  }

  .connect-input:focus {
    border-color: var(--ray-accent, #5b8def);
    box-shadow: 0 0 0 3px rgba(91, 141, 239, 0.15);
  }

  .connect-warn {
    margin: 8px 0 0 0;
    padding: 8px 10px;
    font-size: 12px;
    line-height: 1.4;
    color: #d4a04a;
    background: rgba(212, 160, 74, 0.08);
    border: 1px solid rgba(212, 160, 74, 0.18);
    border-radius: 6px;
  }

  .connect-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }

  .connect-actions-bottom {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid var(--ray-border, #2e2f30);
  }

  .connect-ok {
    margin: 12px 0 0 0;
    font-size: 13px;
    color: #6ab04a;
  }

  .connect-err {
    margin: 12px 0 0 0;
    padding: 8px 10px;
    font-size: 13px;
    line-height: 1.4;
    color: #d96a6a;
    background: rgba(217, 106, 106, 0.08);
    border: 1px solid rgba(217, 106, 106, 0.18);
    border-radius: 6px;
  }

  .connect-reset {
    display: block;
    width: 100%;
    margin-top: 12px;
    padding: 8px;
    font-size: 12px;
    color: var(--ray-text-dim, #8a8d92);
    background: transparent;
    border: none;
    cursor: pointer;
    text-decoration: underline;
  }

  .connect-reset:hover {
    color: var(--ray-text, #f0f1f2);
  }
</style>
