<script lang="ts">
  import { t } from '../../i18n';
  import Input from '../../ui/Input.svelte';
  import Select from '../../ui/Select.svelte';
  import { wizardState } from './wizardState.svelte';

  const MODELS: Record<string, { id: string; label: string }[]> = {
    custom: [{ id: 'custom', label: 'Enter model name...' }],
    'lm-studio': [{ id: 'custom', label: 'Enter model name...' }],
    openai: [
      { id: 'gpt-5.5', label: 'GPT-5.5' },
      { id: 'gpt-5.4', label: 'GPT-5.4' },
      { id: 'gpt-5.2-chat', label: 'GPT-5.2 Chat' },
      { id: 'custom', label: 'Custom model...' },
    ],
    openrouter: [
      { id: 'openai/gpt-oss-120b', label: 'OpenAI: gpt-oss-120b' },
      { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
      { id: 'deepseek/deepseek-v3.2', label: 'DeepSeek V3.2' },
      { id: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
      { id: 'deepseek/deepseek-r1-0528', label: 'DeepSeek: R1 0528' },
      { id: 'google/gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
      { id: 'custom', label: 'Custom model...' },
    ],
  };

  const currentModels = $derived(MODELS[wizardState.selectedProvider] || MODELS.custom);
</script>

<h3 class="card-step-title">{t('setup.model', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.model_hint', wizardState.editLanguage)}</p>
<div class="field-group">
  <label class="field-label">{t('setup.chat_model', wizardState.editLanguage)}</label>
  <Select
    bind:value={wizardState.chatModel}
    options={currentModels.map((m) => ({ label: m.label, value: m.id }))}
  />
</div>
{#if wizardState.chatModel === 'custom'}
  <div class="field-group">
    <label class="field-label">{t('setup.custom_model', wizardState.editLanguage)}</label>
    <Input
      bind:value={wizardState.customModel}
      placeholder={wizardState.selectedProvider === 'lm-studio'
        ? 'e.g. local-model'
        : 'e.g. mistralai/mixtral-8x7b'}
    />
  </div>
{/if}
<div class="field-group">
  <label class="field-label">{t('setup.fast_model', wizardState.editLanguage)}</label>
  <Input bind:value={wizardState.editFastModel} placeholder="gpt-4o-mini" />
  <p class="field-hint">{t('settings.embedding_hint', wizardState.editLanguage)}</p>
</div>
