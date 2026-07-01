<script lang="ts">
  import { t } from '../../i18n';
  import Input from '../../ui/Input.svelte';
  import { wizardState } from './wizardState.svelte';

  let {
    onselectprovider,
    ontestconnection,
  }: {
    onselectprovider: (id: string) => void;
    ontestconnection: () => void;
  } = $props();
</script>

<h3 class="card-step-title">{t('setup.provider', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.provider_hint', wizardState.editLanguage)}</p>
<div class="provider-grid">
  {#each wizardState.providers as p (p.id)}
    <button
      class="provider-btn"
      class:selected={wizardState.selectedProvider === p.id}
      onclick={() => onselectprovider(p.id)}
    >
      <div class="provider-icon">
        {#if p.id === 'openrouter'}🌐
        {:else if p.id === 'openai'}🤖
        {:else if p.id === 'lm-studio'}💻
        {:else if p.id === 'deepseek'}🐋
        {:else if p.id === 'minimax'}🇨🇳
        {:else if p.id === 'grok'}𝕏
        {:else if p.id === 'kimi'}🌙
        {:else if p.id === 'z-ai'}🧠
        {:else if p.id === 'yandexgpt'}🇾
        {:else if p.id === 'gigachat'}💎
        {:else}⚙️
        {/if}
      </div>
      <div class="provider-name">{p.label}</div>
      <div class="provider-desc">{p.description}</div>
    </button>
  {/each}
</div>
{#if wizardState.providers.find((p) => p.id === wizardState.selectedProvider)?.manual_setup}
  <div class="ray-alert info">
    <span class="alert-icon">i</span>
    {t('setup.manual_setup_hint', wizardState.editLanguage)}
  </div>
{/if}
<div class="field-group">
  <label class="field-label">{t('setup.base_url', wizardState.editLanguage)}</label>
  <Input bind:value={wizardState.baseUrl} class="font-mono text-xs" />
</div>
{#if wizardState.providers.find((p) => p.id === wizardState.selectedProvider)?.needs_key}
  <div class="field-group">
    <label class="field-label">{t('setup.api_key', wizardState.editLanguage)}</label>
    <Input
      bind:value={wizardState.apiKey}
      type="password"
      placeholder={wizardState.selectedProvider === 'openrouter' ? 'sk-or-v1-...' : 'sk-...'}
    />
  </div>
{/if}
<div class="test-row">
  <button
    class="ray-btn"
    class:success={wizardState.validated === true}
    class:danger={wizardState.validated === false}
    class:testing={wizardState.validating}
    onclick={ontestconnection}
    disabled={wizardState.validating}
  >
    {#if wizardState.validating}
      <span class="btn-spinner"></span>
      {t('setup.testing', wizardState.editLanguage)}
    {:else if wizardState.validated === true}
      ✓ {t('setup.connected_success', wizardState.editLanguage)}
    {:else if wizardState.validated === false}
      ✗ {t('setup.connection_failed', wizardState.editLanguage)}
    {:else}
      {t('setup.test', wizardState.editLanguage)}
    {/if}
  </button>
</div>

<style>
  /* ─── Provider Grid ─── */
  .provider-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .provider-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 16px 8px;
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .provider-btn:hover {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
  }
  .provider-btn.selected {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .provider-icon {
    font-size: 24px;
  }
  .provider-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .provider-btn.selected .provider-name {
    color: var(--ray-text);
  }
  .provider-desc {
    font-size: 10px;
    font-weight: 400;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    text-align: center;
    line-height: 1.3;
    margin-top: 2px;
  }
</style>
