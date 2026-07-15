<script lang="ts">
  import iconUrl from '../icon.png';

  interface Props {
    /** Optional secondary line (e.g. the API base URL during debugging). */
    detail?: string;
    /** Status message below the title — typically "Starting backend…". */
    message?: string;
    /** Main heading shown under the icon. Defaults to the localized app name. */
    title?: string;
  }

  let { detail, message, title }: Props = $props();
</script>

<div class="splash">
  <div class="splash-card">
    <img class="splash-icon" src={iconUrl} alt="" aria-hidden="true" />
    {#if title}
      <h1 class="splash-title">{title}</h1>
    {/if}
    {#if message}
      <p class="splash-message">{message}</p>
    {/if}
    <div class="splash-spinner" aria-hidden="true"></div>
    {#if detail}
      <code class="splash-detail">{detail}</code>
    {/if}
  </div>
</div>

<style>
  .splash {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--ray-bg);
    z-index: 9999;
  }
  .splash-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 32px 24px;
    max-width: 360px;
    width: 100%;
    text-align: center;
  }
  .splash-icon {
    width: 72px;
    height: 72px;
    border-radius: 18px;
    box-shadow: 0 6px 24px -8px color-mix(in srgb, var(--ray-accent) 40%, transparent);
  }
  .splash-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--ray-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .splash-message {
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 0;
    line-height: 1.5;
    min-height: 1.5em;
  }
  .splash-spinner {
    width: 28px;
    height: 28px;
    border: 3px solid var(--ray-border-strong);
    border-top-color: var(--ray-accent);
    border-radius: 50%;
    animation: splash-spin 0.7s linear infinite;
  }
  .splash-detail {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    background: var(--ray-surface-raised);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 6px;
    padding: 4px 8px;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @keyframes splash-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .splash-spinner {
      animation-duration: 1.5s;
    }
  }
</style>
