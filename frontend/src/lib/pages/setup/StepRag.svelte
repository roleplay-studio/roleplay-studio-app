<script lang="ts">
  import { t } from '../../i18n';
  import Input from '../../ui/Input.svelte';
  import { wizardState } from './wizardState.svelte';
</script>

<h3 class="card-step-title">{t('setup.rag_step_title', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.rag_step_hint', wizardState.editLanguage)}</p>

<label class="rag-toggle">
  <input
    type="checkbox"
    bind:checked={wizardState.enableRag}
    onchange={() => {
      if (!wizardState.enableRag) {
        wizardState.embeddingModel = '';
        wizardState.embeddingBaseUrl = '';
        wizardState.embeddingApiKey = '';
      }
    }}
  />
  <span>{t('setup.rag_enable_label', wizardState.editLanguage)}</span>
</label>

<p class="rag-hint">{t('setup.rag_enable_hint', wizardState.editLanguage)}</p>

{#if wizardState.enableRag}
  <div class="rag-model-field">
    <label class="field-label">{t('setup.rag_model_label', wizardState.editLanguage)}</label>
    <Input
      bind:value={wizardState.embeddingModel}
      placeholder={t('setup.rag_model_placeholder', wizardState.editLanguage)}
    />
    <p class="field-hint">{t('setup.rag_model_hint', wizardState.editLanguage)}</p>
  </div>

  <div class="rag-model-field">
    <label class="field-label">{t('setup.rag_endpoint_label', wizardState.editLanguage)}</label>
    <Input
      bind:value={wizardState.embeddingBaseUrl}
      placeholder={t('setup.rag_endpoint_placeholder', wizardState.editLanguage)}
    />
    <p class="field-hint">{t('setup.rag_endpoint_hint', wizardState.editLanguage)}</p>
  </div>

  <div class="rag-model-field">
    <label class="field-label">{t('setup.rag_api_key_label', wizardState.editLanguage)}</label>
    <Input
      bind:value={wizardState.embeddingApiKey}
      type="password"
      placeholder={t('setup.rag_api_key_placeholder', wizardState.editLanguage)}
    />
    <p class="field-hint">{t('setup.rag_api_key_hint', wizardState.editLanguage)}</p>
  </div>

  <p class="rag-multilingual-hint">
    {t('setup.rag_multilingual_hint', wizardState.editLanguage)}
  </p>

  {#if wizardState.validatingRag}
    <div class="rag-validating">
      <span class="btn-spinner"></span>
      {t('setup.testing', wizardState.editLanguage)}
    </div>
  {/if}
{/if}

<style>
  /* ─── RAG Step ─── */
  .rag-toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: var(--ray-surface-1, rgba(255, 255, 255, 0.04));
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.1));
    border-radius: 10px;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s ease;
    margin-top: 12px;
  }
  .rag-toggle:hover {
    background: var(--ray-surface-2, rgba(255, 255, 255, 0.07));
  }
  .rag-toggle input[type='checkbox'] {
    width: 18px;
    height: 18px;
    accent-color: var(--ray-accent, #4f8cff);
    cursor: pointer;
  }
  .rag-toggle span {
    font-size: 14px;
    font-weight: 500;
  }
  .rag-hint {
    color: var(--ray-text-secondary, rgba(255, 255, 255, 0.6));
    font-size: 13px;
    margin: 8px 0 0 4px;
  }
  .rag-model-field {
    margin-top: 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .rag-multilingual-hint {
    color: var(--ray-text-tertiary, #86868b);
    font-size: 12px;
    font-style: italic;
    margin: 4px 0 0;
    padding: 8px 10px;
    background: var(--ray-surface-raised, #f0f0f2);
    border-radius: 8px;
    letter-spacing: 0.1px;
  }
  .rag-validating {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--ray-text-secondary, rgba(255, 255, 255, 0.6));
    font-size: 13px;
    margin-top: 4px;
  }
  .field-hint {
    font-size: 11px;
    font-weight: 400;
    color: var(--ray-text-tertiary);
    margin: 0;
    letter-spacing: 0.2px;
  }
</style>
