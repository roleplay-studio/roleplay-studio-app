<script lang="ts">
  import { type LLMDebugInfo, type LLMUsage } from './api';

  const {
    debug,
    onclose,
    usage = null,
  }: {
    debug: LLMDebugInfo;
    onclose: () => void;
    usage: LLMUsage | null;
  } = $props();

  // Format a token count for the header line. Matches the style used
  // elsewhere in the app (e.g. chat header stats).
  function formatTokens(n: number): string {
    if (n >= 1000) {
      const k = (n / 1000).toFixed(1);
      return k.endsWith('.0') ? `${Math.round(n / 1000)}k` : `${k}k`;
    }
    return String(n);
  }

  // Pretty-print the model + sampling params for the modal header.
  const headerLine = $derived.by(() => {
    const parts: string[] = [debug.model];
    if (debug.temperature !== null) parts.push(`temp=${debug.temperature}`);
    if (debug.max_tokens !== null) parts.push(`max_tokens=${debug.max_tokens}`);
    return parts.join(' · ');
  });

  // Pretty-printed JSON for the messages array. Kept as a derived
  // string so the modal is reactive to prop changes.
  const messagesJson = $derived(JSON.stringify(debug.messages, null, 2));

  // Escape-to-close + click-outside-to-close. The backdrop click is
  // handled inline; the Escape listener is added in onMount.
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="dbm-overlay" role="presentation" onclick={onclose}>
  <div
    class="dbm-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="dbm-title"
    onclick={(e) => e.stopPropagation()}
  >
    <header class="dbm-header">
      <h3 id="dbm-title" class="dbm-title">🔧 LLM debug payload</h3>
      <button class="dbm-close" onclick={onclose} aria-label="Close" type="button">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"
          ></line></svg
        >
      </button>
    </header>

    <div class="dbm-body">
      <div class="dbm-summary">
        <div class="dbm-model">{headerLine}</div>
        {#if usage}
          <div class="dbm-usage">
            <span class="dbm-usage-pill" title="Tokens in the prompt">
              prompt <strong>{formatTokens(usage.prompt_tokens)}</strong>
            </span>
            <span class="dbm-usage-pill" title="Tokens generated">
              completion <strong>{formatTokens(usage.completion_tokens)}</strong>
            </span>
            <span class="dbm-usage-pill dbm-usage-total" title="Total tokens billed">
              total <strong>{formatTokens(usage.total_tokens)}</strong>
            </span>
          </div>
        {:else}
          <div class="dbm-usage dbm-usage-empty">usage: not provided by model</div>
        {/if}
      </div>

      <section class="dbm-section">
        <h4 class="dbm-section-title">
          Messages sent to LLM
          <span class="dbm-section-meta">{debug.messages.length} turns</span>
        </h4>
        <pre class="dbm-pre">{messagesJson}</pre>
      </section>
    </div>
  </div>
</div>

<style>
  :root {
    --dbm-text: #1d1d1f;
    --dbm-text-secondary: #6e6e73;
    --dbm-text-tertiary: #86868b;
    --dbm-border: rgba(0, 0, 0, 0.08);
    --dbm-bg: #fafafa;
    --dbm-pre-bg: #0f1115;
    --dbm-pre-text: #e7eaee;
    --dbm-accent: #6366f1;
  }
  :root.dark {
    --dbm-text: #f9f9f9;
    --dbm-text-secondary: #9c9c9d;
    --dbm-text-tertiary: #6a6b6c;
    --dbm-border: rgba(255, 255, 255, 0.08);
    --dbm-bg: #14161a;
    --dbm-pre-bg: #08090c;
    --dbm-pre-text: #e7eaee;
    --dbm-accent: #818cf8;
  }

  .dbm-overlay {
    position: fixed;
    inset: 0;
    z-index: 200;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    animation: dbm-fade 0.18s ease-out;
  }

  .dbm-dialog {
    background: var(--ch-bg, #ffffff);
    color: var(--dbm-text);
    border: 1px solid var(--dbm-border);
    border-radius: 12px;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.28);
    min-width: 560px;
    max-width: 80vw;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: dbm-scale 0.18s ease-out;
  }

  .dbm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--dbm-border);
  }
  .dbm-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.3px;
    margin: 0;
  }
  .dbm-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--dbm-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .dbm-close:hover {
    background: rgba(0, 0, 0, 0.06);
    color: var(--dbm-text);
  }

  .dbm-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px 18px;
    overflow: auto;
  }

  .dbm-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--dbm-border);
  }
  .dbm-model {
    font-family: 'Maple Mono', ui-monospace, monospace;
    font-size: 12px;
    font-weight: 600;
    color: var(--dbm-text);
    letter-spacing: 0.3px;
  }
  .dbm-usage {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .dbm-usage-pill {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 500;
    color: var(--dbm-text-secondary);
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid var(--dbm-border);
    background: var(--dbm-bg);
    letter-spacing: 0.2px;
    text-transform: lowercase;
  }
  .dbm-usage-pill strong {
    color: var(--dbm-text);
    font-weight: 600;
    margin-left: 4px;
  }
  .dbm-usage-total {
    background: color-mix(in srgb, var(--dbm-accent) 14%, transparent);
    border-color: color-mix(in srgb, var(--dbm-accent) 30%, transparent);
  }
  .dbm-usage-total strong {
    color: var(--dbm-accent);
  }
  .dbm-usage-empty {
    font-size: 10px;
    color: var(--dbm-text-tertiary);
    font-style: italic;
  }

  .dbm-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .dbm-section-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--dbm-text-tertiary);
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dbm-section-meta {
    font-size: 9px;
    font-weight: 500;
    color: var(--dbm-text-tertiary);
    background: var(--dbm-bg);
    border: 1px solid var(--dbm-border);
    padding: 1px 6px;
    border-radius: 999px;
    letter-spacing: 0.3px;
  }
  .dbm-pre {
    margin: 0;
    padding: 12px 14px;
    background: var(--dbm-pre-bg);
    color: var(--dbm-pre-text);
    border-radius: 8px;
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 11px;
    line-height: 1.55;
    max-height: 50vh;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  @keyframes dbm-fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes dbm-scale {
    from {
      opacity: 0;
      transform: translateY(6px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
