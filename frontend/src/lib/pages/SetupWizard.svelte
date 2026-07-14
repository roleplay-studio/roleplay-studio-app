<script lang="ts">
  import { onMount } from 'svelte';

  import iconUrl from '../../icon.png';
  import { api, API_BASE } from '../api';
  import { availableLangs, currentLang, t } from '../i18n';
  import { Loading } from '../ui';
  import StepFinish from './setup/StepFinish.svelte';
  import StepInterface from './setup/StepInterface.svelte';
  import StepModel from './setup/StepModel.svelte';
  import StepPersona from './setup/StepPersona.svelte';
  import StepProvider from './setup/StepProvider.svelte';
  import StepRag from './setup/StepRag.svelte';
  import StepWelcome from './setup/StepWelcome.svelte';
  import { type Provider, wizardState } from './setup/wizardState.svelte';
  import WizardStepper from './setup/WizardStepper.svelte';

  // Sync currentLang store with wizardState.editLanguage so global
  // i18n (sidebar, modals, etc.) follows the wizard's language choice.
  let prevLang = $state('');
  $effect(() => {
    if (wizardState.editLanguage && wizardState.editLanguage !== prevLang) {
      prevLang = wizardState.editLanguage;
      currentLang.set(wizardState.editLanguage);
    }
  });

  onMount(async () => {
    try {
      const [provRes, langsRes, starterBotsRes] = await Promise.all([
        fetch(`${API_BASE}/api/setup/providers`),
        fetch(`${API_BASE}/api/config/languages`),
        fetch(`${API_BASE}/api/setup/starter-bots`),
      ]);
      if (provRes.ok) {
        // Phase 1.5a: the response is now { providers: [...],
        // selected_provider: "<id>" }. The wizard uses the
        // server-side selected_provider to restore the user's
        // previous choice on reload, instead of clobbering it
        // with whatever happens to be `providers[0].id` (which
        // was always 'custom' or 'openrouter' depending on the
        // iteration order).
        const data: { providers: Provider[]; selected_provider: string } = await provRes.json();
        wizardState.providers = data.providers;
        if (wizardState.providers.length > 0) {
          // Honour the server's selection when it points at a
          // known provider; fall back to whatever is the first
          // catalog entry if the server's claim is unknown
          // (defensive — keeps the dropdown on a valid id even
          // if Settings and the catalog drift apart).
          const knownIds = new Set(wizardState.providers.map((p) => p.id));
          wizardState.selectedProvider = knownIds.has(data.selected_provider)
            ? data.selected_provider
            : wizardState.providers[0].id;
          updateDefaults();
        }
      }
      if (langsRes.ok) {
        wizardState.languages = await langsRes.json();
      } else {
        wizardState.languages = availableLangs();
      }
      // Starter-bot picker (optional — fails silently if no bots_examples/ dir
      // or backend too old to expose the endpoint).
      if (starterBotsRes.ok) {
        wizardState.starterBots = await starterBotsRes.json();
        // Pre-select every working starter bot by default. The user
        // can still untick a card in StepFinish to skip it; this
        // just removes the "import nothing" footgun where the
        // wizard's last step imports zero bots unless the user
        // remembers to check the boxes. Broken cards (parse errors)
        // are excluded — they would fail to import anyway.
        wizardState.selectedStarterBotIds = wizardState.starterBots
          .filter((b: { error?: string; id: string }) => !b.error)
          .map((b: { id: string }) => b.id);
      }

      // Pre-populate RAG state from existing config so a returning user
      // sees their current toggle/model rather than the default off state.
      const config = await api.config();
      if (config?.embedding_model) {
        wizardState.enableRag = true;
        wizardState.embeddingModel = config.embedding_model;
        wizardState.embeddingBaseUrl = config.embedding_base_url ?? '';
        wizardState.embeddingApiKey = config.embedding_api_key_configured ? '••••' : '';
      }
    } catch {
      wizardState.languages = availableLangs();
    } finally {
      wizardState.dataLoading = false;
    }
  });

  function updateDefaults() {
    const p = wizardState.providers.find((x) => x.id === wizardState.selectedProvider);
    if (p) {
      wizardState.baseUrl = p.default_base_url;
      wizardState.apiKey = '';
      // Use the provider's default_model as the suggested chatModel,
      // falling back to 'custom' if the provider has no default
      // (lm-studio and custom have empty default_model).
      wizardState.chatModel = p.default_model || 'custom';
    }
  }

  function selectProvider(id: string) {
    wizardState.selectedProvider = id;
    wizardState.error = '';
    wizardState.validated = null;
    updateDefaults();
  }

  async function testConnection() {
    wizardState.validating = true;
    wizardState.validated = null;
    wizardState.error = '';

    await new Promise((r) => setTimeout(r, 800));

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (wizardState.apiKey.trim()) {
        headers['Authorization'] = `Bearer ${wizardState.apiKey.trim()}`;
      }
      const res = await fetch(`${wizardState.baseUrl.replace(/\/$/, '')}/models`, { headers });
      if (res.ok) {
        const data = await res.json();
        wizardState.validated = true;
        if (
          (wizardState.selectedProvider === 'lm-studio' ||
            wizardState.selectedProvider === 'custom') &&
          data.data?.length
        ) {
          wizardState.chatModel = data.data[0].id;
        }
      } else {
        wizardState.validated = false;
        wizardState.error = `Connection failed (HTTP ${res.status})`;
      }
    } catch (e: any) {
      wizardState.validated = false;
      wizardState.error = `Cannot connect: ${e.message}`;
    } finally {
      wizardState.validating = false;
    }
  }

  async function saveAll() {
    wizardState.loading = true;
    wizardState.error = '';

    const finalModel =
      wizardState.chatModel === 'custom' ? wizardState.customModel.trim() : wizardState.chatModel;

    try {
      // 1. Save provider + bot
      const res = await fetch(`${API_BASE}/api/setup/configure`, {
        body: JSON.stringify({
          api_key: wizardState.apiKey.trim(),
          base_url: wizardState.baseUrl,
          chat_model: finalModel,
          provider: wizardState.selectedProvider,
        }),
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Configuration failed');
      }

      // 2. Save fast model, language, theme, RAG embedding model + endpoint
      const apiKeyChanged =
        wizardState.embeddingApiKey.trim() && wizardState.embeddingApiKey !== '••••';
      await api.updateConfig({
        embedding_api_key: wizardState.enableRag
          ? apiKeyChanged
            ? wizardState.embeddingApiKey.trim()
            : ''
          : '',
        embedding_base_url: wizardState.enableRag ? wizardState.embeddingBaseUrl.trim() : '',
        embedding_model: wizardState.enableRag ? wizardState.embeddingModel.trim() : '',
        fast_model: wizardState.editFastModel || undefined,
        language: wizardState.editLanguage,
        theme: wizardState.editTheme,
      });

      // 3. Create persona if name provided
      if (wizardState.personaName.trim()) {
        await api.createPersona({
          description: wizardState.personaDescription.trim() || undefined,
          name: wizardState.personaName.trim(),
        });
        wizardState.savedPersonaName = wizardState.personaName.trim();
      }

      // 4. Import any selected starter bots. Best-effort: a failure here
      // doesn't abort the setup (the user still gets a working app with
      // the Lili starter + persona). We surface partial failures in
      // wizardState.error so the success screen can mention them.
      if (wizardState.selectedStarterBotIds.length > 0) {
        const importRes = await fetch(`${API_BASE}/api/setup/import-bots`, {
          body: JSON.stringify({ ids: wizardState.selectedStarterBotIds }),
          headers: { 'Content-Type': 'application/json' },
          method: 'POST',
        });
        if (importRes.ok) {
          const result = await importRes.json();
          if (result.skipped && result.skipped.length > 0) {
            wizardState.importedStarterBots = result.imported || [];
            wizardState.failedStarterBots = result.skipped;
          } else {
            wizardState.importedStarterBots = result.imported || [];
            wizardState.failedStarterBots = [];
          }
        } else {
          wizardState.importedStarterBots = [];
          wizardState.failedStarterBots = wizardState.selectedStarterBotIds.map((id) => ({
            id,
            reason: 'import endpoint failed',
          }));
        }
      }

      wizardState.done = true;
    } catch (e: any) {
      wizardState.error = e.message;
    } finally {
      wizardState.loading = false;
    }
  }

  async function nextStep() {
    wizardState.error = '';

    if (wizardState.step === 0) {
      wizardState.step = 1;
    } else if (wizardState.step === 1) {
      wizardState.step = 2;
    } else if (wizardState.step === 2) {
      const provider = wizardState.providers.find((p) => p.id === wizardState.selectedProvider);
      if (provider?.manual_setup) {
        // Skip testConnection for non-OpenAI-compatible providers
        // (YandexGPT, GigaChat). The user will configure these in
        // Settings after the wizard finishes.
        wizardState.validated = true;
      } else {
        await testConnection();
        if (!wizardState.validated) return;
      }
      wizardState.step = 3;
    } else if (wizardState.step === 3) {
      const finalModel =
        wizardState.chatModel === 'custom' ? wizardState.customModel.trim() : wizardState.chatModel;
      if (!finalModel) {
        wizardState.error = t('setup.select_model_error', wizardState.editLanguage);
        return;
      }
      wizardState.step = 4;
    } else if (wizardState.step === 4) {
      if (!wizardState.enableRag) {
        wizardState.step = 5;
        return;
      }
      if (!wizardState.embeddingModel.trim()) {
        wizardState.error = t('setup.rag_model_required', wizardState.editLanguage);
        return;
      }
      if (!wizardState.embeddingBaseUrl.trim()) {
        wizardState.error = t('setup.rag_endpoint_required', wizardState.editLanguage);
        return;
      }
      wizardState.validatingRag = true;
      try {
        await api.validateEmbedding({
          embedding_api_key: wizardState.embeddingApiKey.trim() || null,
          embedding_base_url: wizardState.embeddingBaseUrl.trim(),
          embedding_model: wizardState.embeddingModel.trim(),
        });
        wizardState.step = 5;
      } catch (e: any) {
        wizardState.error = t('setup.rag_endpoint_unreachable', wizardState.editLanguage).replace(
          '{detail}',
          e.message || String(e),
        );
      } finally {
        wizardState.validatingRag = false;
      }
    } else if (wizardState.step === 5) {
      wizardState.step = 6;
    } else if (wizardState.step === 6) {
      await saveAll();
    }
  }

  function prevStep() {
    if (wizardState.step > 0) {
      wizardState.step--;
      wizardState.error = '';
    }
  }

  function finish() {
    window.location.hash = '#/';
    window.location.reload();
  }
</script>

<div class="setup-page">
  {#if wizardState.dataLoading}
    <div class="setup-loading">
      <Loading size="lg" />
    </div>
  {:else if wizardState.done}
    <!-- ─── Done ─── -->
    <div class="setup-done-wrap">
      <div class="ray-card setup-done-card">
        <div class="done-icon">✓</div>
        <h2 class="done-title">{t('setup.all_set', wizardState.editLanguage)} ✨</h2>
        <p class="done-subtitle">
          {t('setup.all_set_hint', wizardState.editLanguage)}
        </p>

        {#if wizardState.savedPersonaName}
          <div class="ready-persona-tag">
            <span class="persona-tag-icon">👤</span>
            {wizardState.savedPersonaName}
          </div>
        {/if}

        {#if wizardState.importedStarterBots.length > 0}
          <div class="ready-bots-section">
            <div class="ready-bots-label">
              ✨ {t('setup.imported_bots', wizardState.editLanguage)}
            </div>
            <div class="ready-bots-list">
              {#each wizardState.importedStarterBots as b (b.bot_id)}
                <span class="ready-bot-chip">{b.name}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if wizardState.failedStarterBots.length > 0}
          <div class="ready-bots-warning">
            ⚠ {t('setup.failed_bots', wizardState.editLanguage)}:
            {wizardState.failedStarterBots.map((b) => b.id).join(', ')}
          </div>
        {/if}

        <button class="ray-btn primary setup-start-btn" onclick={finish}>
          {t('setup.start', wizardState.editLanguage)}
        </button>
      </div>
    </div>
  {:else}
    <!-- ─── Header ─── -->
    {#if wizardState.step > 0}
      <div class="setup-header">
        <div class="setup-logo">
          <img src={iconUrl} alt="logo" class="size-16" />
        </div>
        <h1 class="setup-title">{t('setup.welcome', wizardState.editLanguage)}</h1>
        <p class="setup-subtitle">{t('setup.subtitle', wizardState.editLanguage)}</p>
      </div>
    {/if}

    {#if wizardState.step > 0}
      <WizardStepper />
    {/if}

    <div class="ray-card setup-card step-{wizardState.step}">
      {#if wizardState.step === 0}
        <StepWelcome />
      {:else if wizardState.step === 1}
        <StepInterface />
      {:else if wizardState.step === 2}
        <StepProvider onselectprovider={selectProvider} ontestconnection={testConnection} />
      {:else if wizardState.step === 3}
        <StepModel />
      {:else if wizardState.step === 4}
        <StepRag />
      {:else if wizardState.step === 5}
        <StepPersona />
      {:else if wizardState.step === 6}
        <StepFinish />
      {/if}

      {#if wizardState.error}
        <div class="ray-alert error">
          <span class="alert-icon">!</span>
          {wizardState.error}
        </div>
      {/if}

      <div class="nav-row">
        {#if wizardState.step > 0}
          <button class="ray-btn ghost" onclick={prevStep}>
            {t('setup.back', wizardState.editLanguage)}
          </button>
        {/if}
        <button
          class="ray-btn primary"
          onclick={nextStep}
          disabled={wizardState.loading || wizardState.validating}
        >
          {#if wizardState.loading}
            <span class="btn-spinner"></span>
            {t('setup.saving', wizardState.editLanguage)}
          {:else}
            {wizardState.step === 6
              ? t('setup.save_finish', wizardState.editLanguage)
              : wizardState.step === 2
                ? t('setup.test_continue', wizardState.editLanguage)
                : t('setup.continue', wizardState.editLanguage)}
          {/if}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  /* ─── Raycast Design System ─── */
  :root {
    --ray-bg: #f5f5f7;
    --ray-surface: #ffffff;
    --ray-surface-raised: #f0f0f2;
    --ray-border: rgba(0, 0, 0, 0.06);
    --ray-border-strong: rgba(0, 0, 0, 0.1);
    --ray-border-subtle: rgba(0, 0, 0, 0.04);
    --ray-text: #1d1d1f;
    --ray-text-secondary: #6e6e73;
    --ray-text-tertiary: #86868b;
    --ray-text-dim: #aeaeb2;
    --ray-shadow-ring: rgba(0, 0, 0, 0.04);
    --ray-shadow-inset: rgba(0, 0, 0, 0.02);
    --ray-shadow-btn: rgba(0, 0, 0, 0.06);
    --ray-red: #ff3b30;
    --ray-green: #34c759;
    --ray-blue: hsl(211, 100%, 50%);
    --ray-accent: #8b5cf6;
    --ray-code-bg: rgba(0, 0, 0, 0.04);
    --ray-code-border: rgba(0, 0, 0, 0.06);
    --ray-overlay: #ffffff;
  }
  :root.dark {
    --ray-bg: #07080a;
    --ray-surface: #101111;
    --ray-surface-raised: #1b1c1e;
    --ray-border: rgba(255, 255, 255, 0.06);
    --ray-border-strong: rgba(255, 255, 255, 0.1);
    --ray-border-subtle: rgba(255, 255, 255, 0.04);
    --ray-text: #f9f9f9;
    --ray-text-secondary: #9c9c9d;
    --ray-text-tertiary: #6a6b6c;
    --ray-text-dim: #434345;
    --ray-shadow-ring: rgb(27, 28, 30);
    --ray-shadow-inset: rgb(7, 8, 10);
    --ray-shadow-btn: rgba(255, 255, 255, 0.03);
    --ray-red: #ff6363;
    --ray-green: #5fc992;
    --ray-blue: hsl(202, 100%, 67%);
    --ray-accent: #8b5cf6;
    --ray-code-bg: rgba(255, 255, 255, 0.04);
    --ray-code-border: rgba(255, 255, 255, 0.06);
    --ray-overlay: #1b1c1e;
  }

  /* ─── Page ─── */
  .setup-page {
    min-height: 100vh;
    background: var(--ray-bg);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 24px;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }

  .setup-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 80px 0;
  }

  /* ─── Header ─── */
  .setup-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-bottom: 32px;
    text-align: center;
  }
  .setup-logo {
    margin-bottom: 4px;
  }
  .setup-logo img {
    width: 64px;
    height: 64px;
    border-radius: 16px;
  }
  .setup-title {
    font-size: 22px;
    font-weight: 600;
    margin: 0;
    letter-spacing: 0.2px;
  }
  .setup-subtitle {
    font-size: 14px;
    color: var(--ray-text-secondary);
    margin: 0;
    letter-spacing: 0.2px;
  }

  /* ─── Card ─── */
  .setup-card {
    padding: 32px;
    max-width: 650px;
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
    transition: all 300ms ease;
  }

  .setup-card.step-0 {
    max-width: 1024px;
  }

  .setup-card.step-0 .nav-row {
    justify-content: center;
  }

  .card-step-title {
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 4px;
    letter-spacing: 0.2px;
  }
  .card-step-hint {
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 0 0 12px;
    letter-spacing: 0.2px;
    line-height: 1.5;
  }

  /* ─── Navigation ─── */
  .nav-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    gap: 12px;
  }
  .nav-row .ray-btn {
    min-width: 110px;
  }

  /* ─── Buttons ─── */
  .ray-btn {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    padding: 10px 18px;
    border-radius: 8px;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    letter-spacing: 0.2px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .ray-btn.ghost {
    background: transparent;
    color: var(--ray-text-secondary);
    border-color: var(--ray-border);
  }
  .ray-btn.ghost:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    color: var(--ray-text);
  }
  .ray-btn.ghost.invisible {
    visibility: hidden;
  }
  .ray-btn.primary {
    background: var(--ray-accent);
    color: #fff;
  }
  .ray-btn.primary:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ray-accent) 90%, #fff);
  }
  .ray-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .ray-btn.success {
    background: color-mix(in srgb, var(--ray-green) 20%, transparent);
    color: var(--ray-green);
    border-color: color-mix(in srgb, var(--ray-green) 30%, transparent);
  }
  .ray-btn.danger {
    background: color-mix(in srgb, var(--ray-red) 20%, transparent);
    color: var(--ray-red);
    border-color: color-mix(in srgb, var(--ray-red) 30%, transparent);
  }
  .ray-btn.testing {
    opacity: 0.7;
  }

  .test-row {
    display: flex;
    justify-content: flex-start;
  }

  /* ─── Alert ─── */
  .ray-alert {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
    letter-spacing: 0.2px;
  }
  .ray-alert.error {
    background: color-mix(in srgb, var(--ray-red) 12%, transparent);
    color: var(--ray-red);
    border: 1px solid color-mix(in srgb, var(--ray-red) 25%, transparent);
  }
  .alert-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: currentColor;
    color: var(--ray-bg);
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .btn-spinner {
    width: 12px;
    height: 12px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ─── Done Card ─── */
  .setup-done-wrap {
    display: flex;
    justify-content: center;
    width: 100%;
  }
  .setup-done-card {
    max-width: 480px;
    width: 100%;
    padding: 40px 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
  }
  .done-icon {
    font-size: 48px;
    color: var(--ray-green);
    margin-bottom: 4px;
  }
  .done-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
    letter-spacing: 0.2px;
  }
  .done-subtitle {
    font-size: 13px;
    color: var(--ray-text-secondary);
    margin: 0 0 16px;
    letter-spacing: 0.2px;
    line-height: 1.5;
  }
  .ready-bot-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--ray-surface-raised);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    width: 100%;
    margin-bottom: 4px;
  }
  .ready-bot-avatar {
    flex-shrink: 0;
    color: var(--ray-accent);
  }
  .ready-bot-info {
    flex: 1;
    text-align: left;
    min-width: 0;
  }
  .ready-bot-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--ray-text);
  }
  .ready-bot-msg {
    font-size: 12px;
    color: var(--ray-text-secondary);
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ready-persona-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: color-mix(in srgb, var(--ray-accent) 10%, transparent);
    color: var(--ray-accent);
    border-radius: 86px;
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
  }
  .persona-tag-icon {
    font-size: 14px;
  }
  .ready-bots-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
  }
  .ready-bots-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .ready-bots-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
  }
  .ready-bot-chip {
    display: inline-block;
    padding: 4px 10px;
    background: color-mix(in srgb, var(--ray-green) 12%, transparent);
    color: var(--ray-green);
    border-radius: 86px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid color-mix(in srgb, var(--ray-green) 25%, transparent);
  }
  .ready-bots-warning {
    margin-top: 10px;
    padding: 8px 12px;
    background: color-mix(in srgb, var(--ray-red) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--ray-red) 25%, transparent);
    border-radius: 8px;
    color: var(--ray-red);
    font-size: 12px;
    text-align: left;
    line-height: 1.4;
  }
  .setup-start-btn {
    margin-top: 16px;
    min-width: 160px;
  }
</style>
