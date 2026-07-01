<script lang="ts">
  import { t } from './i18n';

  interface Props {
    /** Last-known backend URL — surfaced so the user can sanity-check. */
    apiBase: string;
    /** Raw error detail (e.g. db_error field from the health response). */
    detail?: string;
    /** Error category from the parent — drives the headline copy. */
    kind: 'degraded' | 'unreachable';
    /** Re-run the readiness check. Should toggle a loading state. */
    onretry: () => void;
    /** While the retry fetch is in flight, disable the button. */
    retrying?: boolean;
    /** HTTP status code, when known (e.g. 503 from /api/health). */
    status?: number;
  }

  let { apiBase: base, detail, kind, onretry, retrying = false, status }: Props = $props();

  let copied = $state(false);

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(base);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      /* clipboard blocked — leave the URL visible so the user can copy manually */
    }
  }
</script>

<div class="error-page">
  <div class="ray-card error-card">
    <div class="error-icon" aria-hidden="true">⚠</div>
    <h2 class="error-title">
      {kind === 'degraded'
        ? t('setup.backend_degraded', 'en')
        : t('setup.backend_unavailable', 'en')}
    </h2>
    <p class="error-subtitle">
      {kind === 'degraded'
        ? t('setup.backend_degraded_hint', 'en')
        : t('setup.backend_unavailable_hint', 'en')}
    </p>

    <div class="error-meta">
      <div class="meta-row">
        <span class="meta-key">URL</span>
        <code class="meta-code">{base}/api/health</code>
        <button class="copy-btn" onclick={copyUrl} type="button">
          {copied ? '✓' : '⧉'}
        </button>
      </div>
      {#if status !== undefined}
        <div class="meta-row">
          <span class="meta-key">HTTP</span>
          <code class="meta-code">{status}</code>
        </div>
      {/if}
      {#if detail}
        <div class="meta-row meta-row-detail">
          <span class="meta-key">Detail</span>
          <code class="meta-code meta-code-detail">{detail}</code>
        </div>
      {/if}
    </div>

    <button class="ray-btn primary retry-btn" onclick={onretry} disabled={retrying} type="button">
      {#if retrying}
        <span class="btn-spinner"></span>
        {t('setup.backend_retrying', 'en')}
      {:else}
        {t('setup.backend_retry', 'en')}
      {/if}
    </button>
  </div>
</div>

<style>
  .error-page {
    min-height: 100vh;
    background: var(--ray-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px 24px;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .error-card {
    max-width: 520px;
    width: 100%;
    padding: 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    text-align: center;
  }
  .error-icon {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--ray-red) 14%, transparent);
    color: var(--ray-red);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    font-weight: 700;
  }
  .error-title {
    font-size: 18px;
    font-weight: 600;
    margin: 0;
    color: var(--ray-text);
    letter-spacing: 0.2px;
  }
  .error-subtitle {
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 0;
    line-height: 1.5;
    letter-spacing: 0.2px;
  }
  .error-meta {
    width: 100%;
    background: var(--ray-surface-raised);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 10px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }
  .meta-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    text-align: left;
  }
  .meta-row-detail {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .meta-key {
    color: var(--ray-text-tertiary);
    font-weight: 500;
    min-width: 48px;
  }
  .meta-code {
    flex: 1;
    background: var(--ray-bg);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 6px;
    padding: 4px 8px;
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 11px;
    color: var(--ray-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .meta-code-detail {
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 120px;
    overflow-y: auto;
    width: 100%;
  }
  .copy-btn {
    background: transparent;
    border: 1px solid var(--ray-border);
    border-radius: 6px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--ray-text-tertiary);
    font-size: 13px;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }
  .copy-btn:hover {
    color: var(--ray-text);
    border-color: var(--ray-border-strong);
  }
  .retry-btn {
    margin-top: 4px;
    min-width: 160px;
  }
  .btn-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    margin-right: 6px;
    vertical-align: middle;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
