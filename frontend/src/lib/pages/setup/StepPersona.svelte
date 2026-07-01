<script lang="ts">
  import { t } from '../../i18n';
  import Input from '../../ui/Input.svelte';
  import Textarea from '../../ui/Textarea.svelte';
  import { wizardState } from './wizardState.svelte';
</script>

<h3 class="card-step-title">{t('setup.persona_title', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.persona_hint', wizardState.editLanguage)}</p>
<div class="field-group">
  <label class="field-label">{t('personas.name', wizardState.editLanguage)}</label>
  <Input
    bind:value={wizardState.personaName}
    placeholder={t('personas.name_placeholder', wizardState.editLanguage)}
  />
</div>
<div class="field-group">
  <label class="field-label">{t('personas.description', wizardState.editLanguage)}</label>
  <Textarea
    bind:value={wizardState.personaDescription}
    placeholder={t('personas.description_placeholder', wizardState.editLanguage)}
    rows={3}
  />
</div>
<p class="skip-hint">{t('setup.persona_skip_hint', wizardState.editLanguage)}</p>

<style>
  /* ─── Skip Hint ─── */
  .skip-hint {
    font-size: 12px;
    font-weight: 400;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    margin: 0;
    text-align: center;
  }
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
</style>
