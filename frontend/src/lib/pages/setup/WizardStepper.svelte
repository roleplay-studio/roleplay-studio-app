<script lang="ts">
  import { t } from '../../i18n';
  import { wizardState } from './wizardState.svelte';

  const stepLabels = $derived([
    t('setup.step_welcome', wizardState.editLanguage),
    t('setup.step_interface', wizardState.editLanguage),
    t('setup.step_provider', wizardState.editLanguage),
    t('setup.step_model', wizardState.editLanguage),
    t('setup.rag_step_title', wizardState.editLanguage),
    t('setup.step_persona', wizardState.editLanguage),
    t('setup.step_finish', wizardState.editLanguage),
  ]);
</script>

<nav class="setup-steps">
  {#each stepLabels as label, i (i)}
    <button
      class="setup-step"
      class:active={wizardState.step === i}
      class:done={wizardState.step > i}
      disabled
    >
      <span class="setup-step-num">
        {#if wizardState.step > i}
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="4 12 10 18 20 6" />
          </svg>
        {:else}
          {i + 1}
        {/if}
      </span>
      <span class="setup-step-label">{label}</span>
    </button>
    {#if i < 6}
      <div class="setup-step-line" class:done={wizardState.step > i}></div>
    {/if}
  {/each}
</nav>

<style>
  /* ─── Steps ─── */
  .setup-steps {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 28px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .setup-step {
    display: flex;
    align-items: center;
    gap: 8px;
    background: none;
    border: none;
    cursor: default;
    padding: 0;
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .setup-step-num {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2px;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border);
    color: var(--ray-text-tertiary);
    transition: all 0.2s ease;
  }
  .setup-step.active .setup-step-num {
    background: var(--ray-accent);
    border-color: var(--ray-accent);
    color: #fff;
    box-shadow:
      color-mix(in srgb, #fff 15%, transparent) 0px 1px 0px inset,
      color-mix(in srgb, #000 25%, transparent) 0px 1px 4px;
  }
  .setup-step.done .setup-step-num {
    background: color-mix(in srgb, var(--ray-green) 12%, transparent);
    border-color: color-mix(in srgb, var(--ray-green) 25%, transparent);
    color: var(--ray-green);
  }
  .setup-step-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    transition: color 0.2s ease;
    white-space: nowrap;
  }
  .setup-step.active .setup-step-label {
    color: var(--ray-text);
  }
  .setup-step.done .setup-step-label {
    color: var(--ray-text-secondary);
  }
  .setup-step-line {
    width: 24px;
    height: 2px;
    background: var(--ray-border);
    border-radius: 1px;
    margin: 0 8px;
    transition: background 0.3s ease;
  }
  .setup-step-line.done {
    background: var(--ray-green);
  }
</style>
