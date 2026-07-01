<script lang="ts">
  import { t } from '../../i18n';
  import { wizardState } from './wizardState.svelte';

  function toggleBot(id: string) {
    const idx = wizardState.selectedStarterBotIds.indexOf(id);
    if (idx === -1) {
      wizardState.selectedStarterBotIds = [...wizardState.selectedStarterBotIds, id];
    } else {
      wizardState.selectedStarterBotIds = wizardState.selectedStarterBotIds.filter((x) => x !== id);
    }
  }

  function isSelected(id: string): boolean {
    return wizardState.selectedStarterBotIds.includes(id);
  }
</script>

<h3 class="card-step-title">{t('setup.ready_title', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.review_settings', wizardState.editLanguage)}</p>
<div class="summary-list">
  <div class="summary-row">
    <span class="summary-key">{t('setup.summary_provider', wizardState.editLanguage)}</span>
    <span class="summary-val badge">
      {wizardState.providers.find((p) => p.id === wizardState.selectedProvider)?.label ||
        wizardState.selectedProvider}
    </span>
  </div>
  <div class="summary-row">
    <span class="summary-key">{t('setup.summary_api_url', wizardState.editLanguage)}</span>
    <code class="summary-code">{wizardState.baseUrl}</code>
  </div>
  {#if wizardState.providers.find((p) => p.id === wizardState.selectedProvider)?.needs_key && wizardState.apiKey}
    <div class="summary-row">
      <span class="summary-key">{t('setup.summary_api_key', wizardState.editLanguage)}</span>
      <span class="summary-val"
        >{wizardState.apiKey.slice(0, 8)}...{wizardState.apiKey.slice(-4)}</span
      >
    </div>
  {/if}
  <div class="summary-row">
    <span class="summary-key">{t('setup.summary_model', wizardState.editLanguage)}</span>
    <code class="summary-code model-code"
      >{wizardState.chatModel === 'custom' ? wizardState.customModel : wizardState.chatModel}</code
    >
  </div>
  {#if wizardState.editFastModel}
    <div class="summary-row">
      <span class="summary-key">{t('setup.summary_fast_model', wizardState.editLanguage)}</span>
      <code class="summary-code">{wizardState.editFastModel}</code>
    </div>
  {/if}
  <div class="summary-row">
    <span class="summary-key">{t('settings.language', wizardState.editLanguage)}</span>
    <span class="summary-val"
      >{wizardState.languages.find((l) => l.id === wizardState.editLanguage)?.label ||
        wizardState.editLanguage}</span
    >
  </div>
  <div class="summary-row">
    <span class="summary-key">{t('settings.theme_title', wizardState.editLanguage)}</span>
    <span class="summary-val">{wizardState.editTheme}</span>
  </div>
  {#if wizardState.personaName.trim()}
    <div class="summary-row">
      <span class="summary-key">{t('setup.summary_persona', wizardState.editLanguage)}</span>
      <span class="summary-val">{wizardState.personaName.trim()}</span>
    </div>
  {/if}
</div>

{#if wizardState.starterBots.length > 0}
  <div class="starter-section">
    <h4 class="starter-section-title">
      {t('setup.starter_bots_title', wizardState.editLanguage)}
    </h4>
    <p class="starter-section-hint">
      {t('setup.starter_bots_hint', wizardState.editLanguage)}
    </p>
    <div class="starter-grid">
      <!--
        Key the each block on `id + format` because the same bot can
        ship as both ``puro.json`` and ``puro.png`` (SillyTavern
        character cards: text + image-with-tEXt-chunks). ``bot.id``
        alone collides and Svelte raises ``each_key_duplicate``.
        Toggling on `id` still works because both cards represent
        the same bot, but a future change that shows the per-format
        file size or original-path would need a different
        selection key.
      -->
      {#each wizardState.starterBots as bot (bot.id + ':' + bot.format)}
        <label class="starter-card" class:selected={isSelected(bot.id)}>
          <input
            type="checkbox"
            checked={isSelected(bot.id)}
            disabled={!!bot.error}
            onchange={() => toggleBot(bot.id)}
            class="starter-card-checkbox"
          />
          <img
            src={bot.avatar_data_url}
            alt={bot.name}
            class="starter-card-avatar"
            width="56"
            height="56"
          />
          <div class="starter-card-body">
            <div class="starter-card-header">
              <span class="starter-card-name">{bot.name}</span>
              <span class="starter-card-format">{bot.format.toUpperCase()}</span>
            </div>
            {#if bot.error}
              <div class="starter-card-error">⚠ {bot.error}</div>
            {:else}
              <p class="starter-card-scenario">{bot.scenario}</p>
            {/if}
          </div>
        </label>
      {/each}
    </div>
  </div>
{/if}

<style>
  /* ─── Summary ─── */
  .summary-list {
    display: flex;
    flex-direction: column;
    gap: 0;
    background: var(--ray-bg);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    overflow: hidden;
  }
  .summary-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    gap: 12px;
  }
  .summary-row + .summary-row {
    border-top: 1px solid var(--ray-border-subtle);
  }
  .summary-key {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
    flex-shrink: 0;
  }
  .summary-val {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .summary-val.badge {
    background: color-mix(in srgb, var(--ray-accent) 12%, transparent);
    color: var(--ray-accent);
    padding: 2px 10px;
    border-radius: 86px;
    font-size: 12px;
    font-weight: 500;
  }
  .summary-code {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 12px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    background: var(--ray-code-bg);
    border: 1px solid var(--ray-code-border);
    border-radius: 6px;
    padding: 3px 8px;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .summary-code.model-code {
    color: var(--ray-accent);
    border-color: color-mix(in srgb, var(--ray-accent) 20%, transparent);
    background: color-mix(in srgb, var(--ray-accent) 8%, transparent);
  }

  /* ─── Starter-bot picker ─── */
  .starter-section {
    margin-top: 8px;
    padding-top: 20px;
    border-top: 1px dashed var(--ray-border);
  }
  .starter-section-title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 4px;
    color: var(--ray-text);
    letter-spacing: 0.2px;
  }
  .starter-section-hint {
    font-size: 12px;
    color: var(--ray-text-tertiary);
    margin: 0 0 14px;
    line-height: 1.5;
  }
  .starter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 10px;
  }
  .starter-card {
    display: flex;
    gap: 12px;
    padding: 12px;
    background: var(--ray-bg);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    cursor: pointer;
    transition:
      border-color 0.15s ease,
      background 0.15s ease;
    position: relative;
  }
  .starter-card:hover {
    border-color: var(--ray-border-strong);
  }
  .starter-card.selected {
    border-color: var(--ray-accent);
    background: color-mix(in srgb, var(--ray-accent) 6%, transparent);
  }
  .starter-card-checkbox {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 16px;
    height: 16px;
    accent-color: var(--ray-accent);
    cursor: pointer;
    margin: 0;
  }
  .starter-card-avatar {
    width: 56px;
    height: 56px;
    border-radius: 10px;
    flex-shrink: 0;
    object-fit: cover;
    background: var(--ray-surface-raised);
  }
  .starter-card-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-right: 24px; /* space for the floating checkbox */
  }
  .starter-card-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .starter-card-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .starter-card-format {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--ray-text-tertiary);
    background: var(--ray-surface-raised);
    padding: 2px 6px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .starter-card-scenario {
    font-size: 12px;
    color: var(--ray-text-secondary);
    line-height: 1.4;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .starter-card-error {
    font-size: 11px;
    color: var(--ray-red);
    line-height: 1.3;
  }
</style>
