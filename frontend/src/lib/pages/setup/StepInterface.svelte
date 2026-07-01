<script lang="ts">
  import { t } from '../../i18n';
  import { applyThemePreference } from '../../theme';
  import Select from '../../ui/Select.svelte';
  import { wizardState } from './wizardState.svelte';

  const themeOptions = $derived([
    { label: t('settings.theme_system', wizardState.editLanguage), value: 'system' },
    { label: t('settings.theme_dark', wizardState.editLanguage), value: 'dark' },
    { label: t('settings.theme_light', wizardState.editLanguage), value: 'light' },
  ]);
</script>

<h3 class="card-step-title">{t('setup.interface', wizardState.editLanguage)}</h3>
<p class="card-step-hint">{t('setup.interface_hint', wizardState.editLanguage)}</p>

<div class="field-group">
  <label class="field-label">{t('settings.language', wizardState.editLanguage)}</label>
  <Select
    bind:value={wizardState.editLanguage}
    options={wizardState.languages.map((l) => ({ label: l.label, value: l.id }))}
  />
</div>

<div class="field-group">
  <label class="field-label">{t('settings.theme_title', wizardState.editLanguage)}</label>
  <div class="theme-options">
    {#each themeOptions as opt (opt.value)}
      <button
        class="theme-btn"
        class:selected={wizardState.editTheme === opt.value}
        onclick={() => {
          wizardState.editTheme = opt.value;
          applyThemePreference(opt.value);
        }}
      >
        {#if opt.value === 'system'}
          <svg
            class="theme-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="2" y="3" width="20" height="14" rx="2" /><line
              x1="8"
              x2="16"
              y1="21"
              y2="21"
            /><line x1="12" x2="12" y1="17" y2="21" />
          </svg>
        {:else if opt.value === 'dark'}
          <svg
            class="theme-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        {:else}
          <svg
            class="theme-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path
              d="m4.93 4.93 1.41 1.41"
            /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path
              d="m6.34 17.66-1.41 1.41"
            /><path d="m19.07 4.93-1.41 1.41" />
          </svg>
        {/if}
        <span>{opt.label}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  /* ─── Field Group ─── */
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

  /* ─── Theme Selector ─── */
  .theme-options {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .theme-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 8px;
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .theme-btn:hover {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
  }
  .theme-btn.selected {
    border-color: var(--ray-accent);
    background: color-mix(in srgb, var(--ray-accent) 10%, transparent);
    color: var(--ray-accent);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .theme-icon {
    flex-shrink: 0;
  }
</style>
