<script lang="ts">
  import { onMount } from 'svelte';

  import {
    api,
    API_BASE,
    type AppConfig,
    reindexEventSource as openReindexStream,
    type ReindexJobState,
  } from '../api';
  import { currentLang, t } from '../i18n';
  import { applyThemePreference, getThemePreference, resolveTheme } from '../theme';
  import { Input, Loading, Modal, Select, Toggle } from '../ui';

  let lang = $state('en');

  onMount(() => currentLang.subscribe((v) => (lang = v)));

  interface Provider {
    default_base_url: string;
    description: string;
    id: string;
    label: string;
    needs_key: boolean;
  }

  interface LangOption {
    id: string;
    label: string;
  }

  let config: AppConfig | null = $state(null);
  let providers: Provider[] = $state([]);
  let languages: LangOption[] = $state([]);
  let loading = $state(true);
  let saving = $state(false);
  let testing = $state(false);
  let tested = $state<boolean | null>(null);
  let testError = $state('');

  // Editable fields
  let editProvider = $state('');
  let editBaseUrl = $state('');
  let editApiKey = $state('');
  let editModel = $state('');
  let editTemperature = $state(0.7);
  let editMaxTokens = $state(500);
  let editEmbedding = $state('');
  let editRagEnabled = $state(false);
  let editFastModel = $state('');
  let editSummarizeEnabled = $state(true);
  let editSummarizeMaxTokens = $state(256);
  let editSummarizeMinLength = $state(100);
  let editThreadSummaryEnabled = $state(true);
  let editThreadSummaryInterval = $state(10);
  let editContextCompressionEnabled = $state(true);
  let editContextCompressionThreshold = $state(50);
  let editContextCompressionKeepRecent = $state(20);
  let editKnowledgeThreshold = $state(0.3);
  let editLanguage = $state('en');
  let themePref = $state('system');
  let saveError = $state('');
  let saved = $state(false);
  let reindexing = $state(false);
  let reindexDone = $state(false);
  let activeTab: 'generation' | 'interface' | 'knowledge' | 'memory' | 'provider' | 'system' =
    $state('provider');

  // Reindex banner / modal (stale-collection rebuild flow)
  let staleBotIds = $state<number[]>([]);
  let reindexJobId = $state<null | string>(null);
  let reindexProgress = $state<null | ReindexJobState>(null);
  let showReindexModal = $state(false);
  let reindexEventSource: EventSource | null = null;
  let reindexError = $state('');

  // Embedding endpoint fields (mirror wizard RAG step)
  let editEmbeddingBaseUrl = $state('');
  let editEmbeddingApiKey = $state('');
  let editEmbeddingApiKeyPlaceholder = ''; // '••••' if key is configured, else ''
  let testingEmbedding = $state(false);
  let embeddingTestResult = $state<null | { detail: string; ok: boolean }>(null);

  // Poll for stale bots on mount. If a reindex is already running, jump
  // straight to the modal so the user sees its progress.
  async function refreshKnowledgeStatus() {
    try {
      const s = await api.getKnowledgeStatus();
      staleBotIds = s.stale_bot_ids ?? [];
      if (s.reindex_in_progress && s.reindex_job_id) {
        reindexJobId = s.reindex_job_id;
        showReindexModal = true;
        subscribeReindexStream(s.reindex_job_id);
      }
    } catch (e) {
      // Non-fatal: the page still works without the banner.
      console.warn('getKnowledgeStatus failed', e);
    }
  }

  $effect(() => {
    refreshKnowledgeStatus();
  });

  function subscribeReindexStream(jobId: string) {
    if (reindexEventSource) {
      reindexEventSource.close();
      reindexEventSource = null;
    }
    const es = openReindexStream(jobId);
    reindexEventSource = es;
    es.addEventListener('progress', (e: Event) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as ReindexJobState;
        reindexProgress = data;
        if (
          data.status === 'completed' ||
          data.status === 'failed' ||
          data.status === 'cancelled'
        ) {
          es.close();
          reindexEventSource = null;
          if (data.status === 'completed') {
            staleBotIds = [];
            reindexDone = true;
          } else if (data.status === 'failed') {
            reindexError = data.error ?? 'Reindex failed';
          }
        }
      } catch (parseErr) {
        console.warn('reindex progress parse failed', parseErr);
      }
    });
  }

  async function startReindex() {
    reindexError = '';
    try {
      const result = await api.startReindex();
      if (!result.job_id) {
        // Nothing to do — server reported zero stale bots.
        staleBotIds = [];
        return;
      }
      reindexJobId = result.job_id;
      reindexProgress = null;
      showReindexModal = true;
      subscribeReindexStream(result.job_id);
    } catch (e: any) {
      // 409 means a reindex is already running server-side; open the modal
      // and let the SSE stream report progress.
      if (String(e?.message ?? e).includes('409')) {
        showReindexModal = true;
        await refreshKnowledgeStatus();
      } else {
        reindexError = e?.message ?? 'Reindex failed to start';
      }
    }
  }

  async function cancelReindex() {
    if (reindexEventSource) {
      reindexEventSource.close();
      reindexEventSource = null;
    }
    if (reindexJobId) {
      try {
        await api.cancelReindex(reindexJobId);
      } catch {
        // ignore — job may have already finished
      }
    }
    showReindexModal = false;
    reindexJobId = null;
    reindexProgress = null;
  }

  async function testEmbeddingEndpoint() {
    if (!editEmbedding.trim() || !editEmbeddingBaseUrl.trim()) {
      embeddingTestResult = { detail: 'Model and URL are required.', ok: false };
      return;
    }
    testingEmbedding = true;
    embeddingTestResult = null;
    try {
      await api.validateEmbedding({
        embedding_api_key:
          editEmbeddingApiKey && editEmbeddingApiKey !== '••••' ? editEmbeddingApiKey.trim() : null,
        embedding_base_url: editEmbeddingBaseUrl.trim(),
        embedding_model: editEmbedding.trim(),
      });
      embeddingTestResult = { detail: 'Endpoint reachable.', ok: true };
    } catch (e: any) {
      embeddingTestResult = { detail: String(e?.message ?? e), ok: false };
    } finally {
      testingEmbedding = false;
    }
  }

  onMount(async () => {
    try {
      const [cfg, provs, langs] = await Promise.all([
        api.config(),
        fetch(`${API_BASE}/api/setup/providers`).then((r) => r.json()),
        fetch(`${API_BASE}/api/config/languages`).then((r) => r.json()),
      ]);
      config = cfg;
      providers = provs;
      languages = langs;
      editProvider = 'openrouter';
      editBaseUrl = cfg.openrouter_base_url;
      editModel = cfg.chat_model;
      editTemperature = cfg.default_temperature;
      editMaxTokens = cfg.default_max_tokens;
      editEmbedding = cfg.embedding_model;
      editRagEnabled = !!cfg.embedding_model?.trim();
      editEmbeddingBaseUrl = cfg.embedding_base_url ?? '';
      editEmbeddingApiKeyPlaceholder = cfg.embedding_api_key_configured ? '••••' : '';
      editEmbeddingApiKey = ''; // user must type to change
      embeddingTestResult = null;
      editFastModel = cfg.fast_model;
      editSummarizeEnabled = cfg.summarize_enabled;
      editSummarizeMaxTokens = cfg.summarize_max_tokens ?? 256;
      editSummarizeMinLength = cfg.summarize_min_length ?? 100;
      editThreadSummaryEnabled = cfg.thread_summary_enabled;
      editThreadSummaryInterval = cfg.thread_summary_interval ?? 10;
      editContextCompressionEnabled = cfg.context_compression_enabled;
      editContextCompressionThreshold = cfg.context_compression_threshold ?? 50;
      editContextCompressionKeepRecent = cfg.context_compression_keep_recent ?? 20;
      editKnowledgeThreshold = cfg.knowledge_relevance_threshold ?? 0.3;
      editLanguage = cfg.language || 'en';
      themePref = getThemePreference();
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  function selectProvider(id: string) {
    editProvider = id;
    const p = providers.find((x) => x.id === id);
    if (p) editBaseUrl = p.default_base_url;
  }

  async function testConnection() {
    testing = true;
    tested = null;
    testError = '';
    await new Promise((r) => setTimeout(r, 600));
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (editApiKey.trim()) headers['Authorization'] = `Bearer ${editApiKey.trim()}`;
      const res = await fetch(`${editBaseUrl.replace(/\/$/, '')}/models`, { headers });
      if (res.ok) {
        tested = true;
        const data = await res.json();
        if (
          data.data?.length &&
          providers.find((p) => p.id === editProvider)?.id !== 'openrouter' &&
          editModel === config?.chat_model
        ) {
          editModel = data.data[0].id;
        }
      } else {
        tested = false;
        testError = `HTTP ${res.status}`;
      }
    } catch (e: any) {
      tested = false;
      testError = e.message;
    } finally {
      testing = false;
    }
  }

  async function saveAll() {
    saving = true;
    saveError = '';
    saved = false;
    try {
      // Provider / chat (uses /api/setup/configure because it has provider-specific logic)
      const res = await fetch(`${API_BASE}/api/setup/configure`, {
        body: JSON.stringify({
          api_key: editApiKey,
          base_url: editBaseUrl,
          chat_model: editModel,
          provider: editProvider,
        }),
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Save failed');
      }
      // Everything else via the general config endpoint
      config = await api.updateConfig({
        context_compression_enabled: editContextCompressionEnabled,
        context_compression_keep_recent: editContextCompressionKeepRecent,
        context_compression_threshold: editContextCompressionThreshold,
        // Only send the API key if the user typed something new (not the
        // "••••" placeholder, which means "key is configured, don't change").
        embedding_api_key:
          editEmbeddingApiKey && editEmbeddingApiKey !== '••••' ? editEmbeddingApiKey : '',
        embedding_base_url: editEmbeddingBaseUrl,
        embedding_model: editEmbedding,
        fast_model: editFastModel,
        knowledge_relevance_threshold: editKnowledgeThreshold,
        language: editLanguage,
        max_tokens: editMaxTokens,
        summarize_enabled: editSummarizeEnabled,
        summarize_max_tokens: editSummarizeMaxTokens,
        summarize_min_length: editSummarizeMinLength,
        temperature: editTemperature,
        thread_summary_enabled: editThreadSummaryEnabled,
        thread_summary_interval: editThreadSummaryInterval,
      });
      saved = true;
      setTimeout(() => (saved = false), 3000);
    } catch (e: any) {
      saveError = e?.message ?? String(e);
    } finally {
      saving = false;
    }
  }

  async function changeTheme(value: string) {
    themePref = value;
    applyThemePreference(value);
    try {
      await api.updateConfig({ theme: value });
    } catch {
      /* ignore */
    }
  }
</script>

<div class="settings-page">
  <header class="settings-header">
    <div>
      <h1 class="settings-title">{t('settings.title', lang)}</h1>
      <p class="settings-subtitle">{t('settings.subtitle', lang)}</p>
    </div>
    {#if saved}
      <div class="saved-badge">{t('common.saved', lang)}</div>
    {/if}
  </header>

  {#if loading}
    <div class="loading-wrap">
      <Loading size="lg" />
    </div>
  {:else}
    <div class="settings-layout">
      <!-- Tab navigation -->
      <nav class="settings-tabs">
        <button
          class="settings-tab"
          class:active={activeTab === 'provider'}
          onclick={() => (activeTab = 'provider')}
        >
          <span class="tab-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-sparkles-icon lucide-sparkles"
              ><path
                d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"
              /><path d="M20 2v4" /><path d="M22 4h-4" /><circle cx="4" cy="20" r="2" /></svg
            >
          </span>
          <span class="tab-label">{t('settings.provider', lang)}</span>
        </button>
        <button
          class="settings-tab"
          class:active={activeTab === 'generation'}
          onclick={() => (activeTab = 'generation')}
        >
          <span class="tab-icon"
            ><svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-message-square-text-icon lucide-message-square-text"
              ><path
                d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z"
              /><path d="M7 11h10" /><path d="M7 15h6" /><path d="M7 7h8" /></svg
            ></span
          >
          <span class="tab-label">{t('settings.tab_generation', lang)}</span>
        </button>
        <button
          class="settings-tab"
          class:active={activeTab === 'memory'}
          onclick={() => (activeTab = 'memory')}
        >
          <span class="tab-icon"
            ><svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-brain-icon lucide-brain"
              ><path d="M12 18V5" /><path d="M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4" /><path
                d="M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5"
              /><path d="M17.997 5.125a4 4 0 0 1 2.526 5.77" /><path
                d="M18 18a4 4 0 0 0 2-7.464"
              /><path d="M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517" /><path
                d="M6 18a4 4 0 0 1-2-7.464"
              /><path d="M6.003 5.125a4 4 0 0 0-2.526 5.77" /></svg
            ></span
          >
          <span class="tab-label">{t('settings.tab_memory', lang)}</span>
        </button>
        <button
          class="settings-tab"
          class:active={activeTab === 'knowledge'}
          onclick={() => (activeTab = 'knowledge')}
        >
          <span class="tab-icon"
            ><svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-book-text-icon lucide-book-text"
              ><path
                d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"
              /><path d="M8 11h8" /><path d="M8 7h6" /></svg
            ></span
          >
          <span class="tab-label">{t('settings.tab_knowledge', lang)}</span>
        </button>
        <button
          class="settings-tab"
          class:active={activeTab === 'interface'}
          onclick={() => (activeTab = 'interface')}
        >
          <span class="tab-icon"
            ><svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-sun-icon lucide-sun"
              ><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path
                d="m4.93 4.93 1.41 1.41"
              /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path
                d="m6.34 17.66-1.41 1.41"
              /><path d="m19.07 4.93-1.41 1.41" /></svg
            ></span
          >
          <span class="tab-label">{t('settings.tab_interface', lang)}</span>
        </button>
        <button
          class="settings-tab"
          class:active={activeTab === 'system'}
          onclick={() => (activeTab = 'system')}
        >
          <span class="tab-icon"
            ><svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-badge-info-icon lucide-badge-info"
              ><path
                d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"
              /><line x1="12" x2="12" y1="16" y2="12" /><line
                x1="12"
                x2="12.01"
                y1="8"
                y2="8"
              /></svg
            ></span
          >
          <span class="tab-label">System</span>
        </button>

        <div class="settings-save-bar">
          <!-- <div class="settings-save-status">
          {#if saved}
            <span class="settings-save-ok">✓ {t('settings.save_all_saved', lang)}</span>
          {:else if saveError}
            <span class="settings-save-fail">
              ✗ {t('settings.save_all_partial', lang).replace('{detail}', saveError)}
            </span>
          {/if}
        </div> -->
          <button class="ray-btn primary w-full justify-center" onclick={saveAll} disabled={saving}>
            {#if saving}
              <span class="btn-spinner"></span>
            {/if}
            {t('settings.save_all', lang)}
          </button>
        </div>
      </nav>

      {#if activeTab === 'provider'}
        <section class="settings-section">
          <div class="ray-card">
            <div class="provider-grid">
              {#each providers as p (p.id)}
                <button
                  class="provider-btn"
                  class:selected={editProvider === p.id}
                  onclick={() => selectProvider(p.id)}
                >
                  <div class="provider-icon">
                    {#if p.id === 'openrouter'}🌐{:else if p.id === 'openai'}🤖{:else if p.id === 'lm-studio'}💻{:else}⚙️{/if}
                  </div>
                  <div class="provider-name">{p.label}</div>
                </button>
              {/each}
            </div>

            <div class="field-group">
              <label class="field-label">Base URL</label>
              <Input bind:value={editBaseUrl} placeholder="https://openrouter.ai/api/v1" />
            </div>

            <div class="field-group">
              <label class="field-label">API Key</label>
              <Input bind:value={editApiKey} type="password" placeholder="sk-..." />
            </div>

            <div class="field-group">
              <label class="field-label">{t('settings.model', lang)}</label>
              <Input bind:value={editModel} placeholder="gpt-4o" />
            </div>

            <div class="field-group">
              <label class="field-label">{t('settings.fast_model', lang)}</label>
              <Input bind:value={editFastModel} placeholder="gpt-4o-mini" />
              <p class="field-hint">
                {t('settings.fast_model_hint', lang)}
              </p>
            </div>

            <div class="action-row">
              <button
                class="ray-btn"
                class:primary={tested === true}
                class:danger={tested === false}
                onclick={testConnection}
                disabled={testing}
              >
                {#if testing}
                  <span class="btn-spinner"></span>
                  Testing...
                {:else if tested === true}
                  ✓ Connected
                {:else if tested === false}
                  ✗ Failed
                {:else}
                  Test Connection
                {/if}
              </button>
            </div>

            {#if testError}
              <div class="ray-alert error">
                <span class="alert-icon">!</span>
                {testError}
              </div>
            {/if}
            {#if saveError}
              <div class="ray-alert error">
                <span class="alert-icon">!</span>
                {saveError}
              </div>
            {/if}
          </div>
        </section>
      {/if}

      {#if activeTab === 'generation'}
        <section class="settings-section">
          <div class="ray-card">
            <div class="two-col">
              <div class="field-group">
                <label class="field-label">Temperature</label>
                <div class="range-wrap">
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.05"
                    bind:value={editTemperature}
                    class="ray-range"
                  />
                  <code class="range-value">{editTemperature.toFixed(2)}</code>
                </div>
                <p class="field-hint">Lower = focused, higher = creative</p>
              </div>
              <div class="field-group">
                <label class="field-label">{t('settings.max_tokens', lang)}</label>
                <div class="range-wrap">
                  <input
                    type="range"
                    min="128"
                    max="8192"
                    step="128"
                    bind:value={editMaxTokens}
                    class="ray-range"
                  />
                  <code class="range-value">{editMaxTokens}</code>
                </div>
                <p class="field-hint">{t('settings.max_tokens_hint', lang)}</p>
              </div>
            </div>
          </div>
        </section>
      {/if}

      {#if activeTab === 'memory'}
        <section class="settings-section">
          <div class="ray-card">
            <h3 class="subsection-title">Summarization</h3>
            <p class="section-hint">{t('settings.memory_section_hint', lang)}</p>

            <div class="field-group">
              <div class="toggle-row">
                <div>
                  <label class="field-label">{t('settings.summarize_enabled_label', lang)}</label>
                  <p class="field-hint">
                    {t('settings.summarize_enabled_hint', lang)}
                  </p>
                </div>
                <Toggle bind:checked={editSummarizeEnabled} />
              </div>
            </div>

            {#if editSummarizeEnabled}
              <div class="field-group">
                <label class="field-label">{t('settings.max_tokens', lang)}</label>
                <div class="range-wrap">
                  <input
                    type="range"
                    min="32"
                    max="512"
                    step="16"
                    bind:value={editSummarizeMaxTokens}
                    class="ray-range"
                  />
                  <code class="range-value">{editSummarizeMaxTokens}</code>
                </div>
                <p class="field-hint">
                  {t('settings.summarize_max_tokens_hint', lang)}
                </p>
              </div>

              <div class="field-group">
                <label class="field-label">{t('settings.summarize_min_length', lang)}</label>
                <div class="range-wrap">
                  <input
                    type="range"
                    min="20"
                    max="500"
                    step="10"
                    bind:value={editSummarizeMinLength}
                    class="ray-range"
                  />
                  <code class="range-value">{editSummarizeMinLength} chars</code>
                </div>
                <p class="field-hint">
                  {t('settings.summarize_min_length_hint', lang)}
                </p>
              </div>

              <div class="field-group">
                <div class="toggle-row">
                  <div>
                    <label class="field-label">{t('settings.thread_summary_enabled', lang)}</label>
                    <p class="field-hint">
                      {t('settings.thread_summary_enabled_hint', lang)}
                    </p>
                  </div>
                  <Toggle bind:checked={editThreadSummaryEnabled} />
                </div>
              </div>

              {#if editThreadSummaryEnabled}
                <div class="field-group">
                  <label class="field-label">{t('settings.thread_summary_interval', lang)}</label>
                  <div class="range-wrap">
                    <input
                      type="range"
                      min="3"
                      max="30"
                      step="1"
                      bind:value={editThreadSummaryInterval}
                      class="ray-range"
                    />
                    <code class="range-value">Every {editThreadSummaryInterval} msgs</code>
                  </div>
                  <p class="field-hint">
                    {t('settings.thread_summary_interval_hint', lang)}
                  </p>
                </div>
              {/if}
            {/if}

            <div class="section-divider"></div>
            <h3 class="subsection-title">{t('settings.memory_section_title', lang)}</h3>

            <div class="field-group">
              <div class="toggle-row">
                <div>
                  <label class="field-label"
                    >{t('settings.context_compression_enabled', lang)}</label
                  >
                  <p class="field-hint">
                    {t('settings.context_compression_enabled_hint', lang)}
                  </p>
                </div>
                <Toggle bind:checked={editContextCompressionEnabled} />
              </div>
            </div>

            {#if editContextCompressionEnabled}
              <div class="field-group">
                <label class="field-label"
                  >{t('settings.context_compression_threshold_label', lang)}</label
                >
                <div class="range-wrap">
                  <input
                    type="range"
                    min="10"
                    max="1000"
                    step="5"
                    bind:value={editContextCompressionThreshold}
                    class="ray-range"
                  />
                  <code class="range-value">{editContextCompressionThreshold} msgs</code>
                </div>
                <p class="field-hint">
                  {t('settings.context_compression_threshold_hint', lang)}
                </p>
              </div>

              <div class="field-group">
                <label class="field-label"
                  >{t('settings.context_compression_keep_recent_label', lang)}</label
                >
                <div class="range-wrap">
                  <input
                    type="range"
                    min="5"
                    max="500"
                    step="1"
                    bind:value={editContextCompressionKeepRecent}
                    class="ray-range"
                  />
                  <code class="range-value">{editContextCompressionKeepRecent} msgs</code>
                </div>
                <p class="field-hint">
                  {t('settings.context_compression_keep_recent_hint', lang)}
                </p>
              </div>
            {/if}
          </div>
        </section>
      {/if}

      {#if activeTab === 'knowledge'}
        <section class="settings-section">
          <div class="ray-card">
            <h3 class="subsection-title">{t('settings.knowledge_section_title', lang)}</h3>
            <p class="section-hint">{t('settings.knowledge_section_hint', lang)}</p>

            {#if staleBotIds.length > 0 && !showReindexModal}
              <div class="reindex-banner" role="status" aria-live="polite">
                <div class="reindex-banner-text">
                  <strong>{t('reindex.banner_title', lang)}</strong>
                  <p>
                    {t('reindex.banner_body', lang).replace('{count}', String(staleBotIds.length))}
                  </p>
                </div>
                <button class="ray-btn primary" onclick={startReindex} type="button">
                  {t('reindex.banner_action_all', lang)}
                </button>
              </div>
            {/if}
            {#if reindexError}
              <div class="ray-alert error" role="alert">
                <span class="alert-icon">!</span>
                {reindexError}
              </div>
            {/if}

            <div class="field-group">
              <div class="toggle-row">
                <div>
                  <label class="field-label">{t('settings.rag_section_title', lang)}</label>
                  <p class="field-hint">{t('settings.rag_section_hint', lang)}</p>
                </div>
                <Toggle
                  checked={editRagEnabled}
                  onchange={(e) => {
                    const next = (e.currentTarget as HTMLInputElement).checked;
                    editRagEnabled = next;
                    if (!next) {
                      // Disable: clear the model so saveAll sends '' to the API.
                      editEmbedding = '';
                    } else if (!editEmbedding.trim() && config?.embedding_model) {
                      // Re-enable: keep the last known model so the user doesn't
                      // have to retype it (e.g. toggling off and on to test).
                      editEmbedding = config.embedding_model;
                    }
                  }}
                />
              </div>
              <span
                class="rag-status-badge"
                class:rag-status-active={editRagEnabled}
                class:rag-status-disabled={!editRagEnabled}
              >
                {editRagEnabled ? t('settings.rag_active', lang) : t('settings.rag_disabled', lang)}
              </span>
              <label class="field-label rag-model-label">{t('setup.rag_model_label', lang)}</label>
              <Input
                bind:value={editEmbedding}
                placeholder={t('setup.rag_model_placeholder', lang)}
              />
              <p class="field-hint">{t('setup.rag_model_hint', lang)}</p>

              <label class="field-label rag-model-label"
                >{t('setup.rag_endpoint_label', lang)}</label
              >
              <Input
                bind:value={editEmbeddingBaseUrl}
                placeholder={t('setup.rag_endpoint_placeholder', lang)}
              />
              <p class="field-hint">{t('setup.rag_endpoint_hint', lang)}</p>

              <label class="field-label rag-model-label">{t('setup.rag_api_key_label', lang)}</label
              >
              <Input
                type="password"
                bind:value={editEmbeddingApiKey}
                placeholder={editEmbeddingApiKeyPlaceholder ||
                  t('setup.rag_api_key_placeholder', lang)}
              />
              <p class="field-hint">{t('setup.rag_api_key_hint', lang)}</p>

              <div class="rag-test-row">
                <button
                  type="button"
                  class="ray-btn ray-btn-secondary"
                  onclick={testEmbeddingEndpoint}
                  disabled={testingEmbedding ||
                    !editEmbedding.trim() ||
                    !editEmbeddingBaseUrl.trim()}
                >
                  {testingEmbedding ? '...' : 'Test connection'}
                </button>
                {#if embeddingTestResult}
                  <span
                    class="rag-test-result"
                    class:rag-test-ok={embeddingTestResult.ok}
                    class:rag-test-fail={!embeddingTestResult.ok}
                  >
                    {embeddingTestResult.ok ? '✓' : '✗'}
                    {embeddingTestResult.detail}
                  </span>
                {/if}
              </div>
              <p class="field-hint rag-multilingual-hint">
                {t('setup.rag_multilingual_hint', lang)}
              </p>
            </div>

            <div class="field-group">
              <label class="field-label">{t('settings.rag_threshold_label', lang)}</label>
              <div class="range-wrap">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  bind:value={editKnowledgeThreshold}
                  class="ray-range"
                />
                <code class="range-value">{editKnowledgeThreshold.toFixed(2)}</code>
              </div>
              <p class="field-hint">
                {t('settings.rag_threshold_hint', lang)}
              </p>
            </div>

            <div class="action-row">
              <button
                class="ray-btn"
                onclick={async () => {
                  reindexing = true;
                  reindexDone = false;
                  try {
                    await api.reindexKnowledge();
                    reindexDone = true;
                  } catch {
                    alert(t('reindex.modal_title', lang) + ' failed');
                  } finally {
                    reindexing = false;
                  }
                }}
                disabled={reindexing}
              >
                {#if reindexing}
                  <span class="btn-spinner"></span>
                {/if}
                Reindex Knowledge Base
              </button>
              {#if reindexDone}
                <span class="rag-status-badge rag-status-active">{t('common.done', lang)}</span>
              {/if}
            </div>
          </div>
        </section>
      {/if}

      {#if activeTab === 'interface'}
        <section class="settings-section">
          <div class="ray-card">
            <div class="field-group">
              <label class="field-label">Language</label>
              <Select
                bind:value={editLanguage}
                options={languages.map((l) => ({ label: l.label, value: l.id }))}
              />
            </div>

            <h3 class="subsection-title">Theme</h3>
            <div class="theme-grid">
              <button
                class="theme-btn"
                class:selected={themePref === 'dark'}
                onclick={() => changeTheme('dark')}
              >
                <div class="theme-icon">🌙</div>
                <div class="theme-name">Dark</div>
              </button>
              <button
                class="theme-btn"
                class:selected={themePref === 'light'}
                onclick={() => changeTheme('light')}
              >
                <div class="theme-icon">☀️</div>
                <div class="theme-name">Light</div>
              </button>
              <button
                class="theme-btn"
                class:selected={themePref === 'system'}
                onclick={() => changeTheme('system')}
              >
                <div class="theme-icon">🔄</div>
                <div class="theme-name">System</div>
              </button>
            </div>
            <p class="theme-hint">
              {#if themePref === 'system'}
                Current: {resolveTheme('system') ? '🌙 dark' : '☀️ light'} (follows system)
              {:else if themePref === 'dark'}
                Always dark, regardless of system
              {:else}
                Always light, regardless of system
              {/if}
            </p>
          </div>
        </section>
      {/if}

      {#if activeTab === 'system'}
        <section class="settings-section">
          <div class="ray-card">
            <div class="config-list">
              <div class="config-row">
                <div class="config-key">Version</div>
                <code class="config-code">{config!.version}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Environment</div>
                <code class="config-code">
                  {config!.environment}
                  {#if config!.environment === 'development'}
                    <span class="env-badge">dev mode</span>
                  {/if}
                </code>
              </div>
              <div class="config-row">
                <div class="config-key">Debug Mode</div>
                <div class="config-val">
                  <span class:green={config!.debug_enabled} class:red={!config!.debug_enabled}>
                    {config!.debug_enabled ? 'on' : 'off'}
                  </span>
                  <span
                    class="status-dot"
                    class:green={config!.debug_enabled}
                    class:red={!config!.debug_enabled}
                  ></span>
                  {#if config!.debug_env_raw}
                    <span class="config-meta">(DEBUG={config!.debug_env_raw})</span>
                  {/if}
                </div>
              </div>
              <div class="config-row">
                <div class="config-key">API Status</div>
                <div class="config-val">
                  <span
                    class:green={config!.api_key_configured}
                    class:red={!config!.api_key_configured}
                  >
                    {config!.api_key_configured ? 'configured' : 'missing'}
                  </span>
                  <span
                    class="status-dot"
                    class:green={config!.api_key_configured}
                    class:red={!config!.api_key_configured}
                  ></span>
                </div>
              </div>
              <div class="config-row">
                <div class="config-key">Model</div>
                <code class="config-code">{config!.chat_model}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Fast Model</div>
                <code class="config-code">{config!.fast_model || '—'}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Base URL</div>
                <code class="config-code">{config!.openrouter_base_url}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Temperature</div>
                <code class="config-code">{config!.default_temperature}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Max Tokens</div>
                <code class="config-code">{config!.default_max_tokens}</code>
              </div>
              <div class="config-row">
                <div class="config-key">History Limit</div>
                <code class="config-code">{config!.history_limit}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Knowledge base (RAG)</div>
                <code class="config-code">{config!.embedding_model || 'off'}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Summarize</div>
                <code class="config-code"
                  >{config!.summarize_enabled ? 'on' : 'off'}{config!.thread_summary_enabled
                    ? ', thread summary every ' + config!.thread_summary_interval + ' msgs'
                    : ''}{config!.summarize_enabled
                    ? ', max ' +
                      config!.summarize_max_tokens +
                      ' tok, min ' +
                      config!.summarize_min_length +
                      ' chars'
                    : ''}</code
                >
              </div>
              <div class="config-row">
                <div class="config-key">Compression</div>
                <code class="config-code"
                  >{config!.context_compression_enabled
                    ? 'on, threshold ' +
                      config!.context_compression_threshold +
                      ', keep ' +
                      config!.context_compression_keep_recent +
                      ' recent'
                    : 'off'}</code
                >
              </div>
              <div class="config-row">
                <div class="config-key">RAG Threshold</div>
                <code class="config-code">{config!.knowledge_relevance_threshold}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Language</div>
                <code class="config-code">{config!.language}</code>
              </div>
              <div class="config-row">
                <div class="config-key">DB Path</div>
                <code class="config-code">{config!.db_path}</code>
              </div>
              <div class="config-row">
                <div class="config-key">Chroma Dir</div>
                <code class="config-code">{config!.chroma_persist_dir}</code>
              </div>
            </div>
          </div>
        </section>
      {/if}
    </div>
  {/if}
</div>

<!-- Reindex progress modal — opened when startReindex is called or when a
     reindex was already running when the page mounted. -->
<Modal open={showReindexModal} title={t('reindex.modal_title', lang)} onclose={cancelReindex}>
  <div class="reindex-modal-body">
    {#if reindexProgress}
      <p class="reindex-modal-bot">
        {#if reindexProgress.current_bot_name}
          {reindexProgress.current_bot_name}
        {:else}
          …
        {/if}
      </p>
      <progress
        class="reindex-modal-progress"
        value={reindexProgress.current_bot_entries_done}
        max={reindexProgress.current_bot_entries_total || 1}
      ></progress>
      <p class="reindex-modal-count">
        {reindexProgress.current_bot_entries_done} / {reindexProgress.current_bot_entries_total}
      </p>
      <p class="reindex-modal-status">
        Status: {reindexProgress.status} ({reindexProgress.bots_done}/{reindexProgress.total_bots} bots)
      </p>
    {:else}
      <p class="reindex-modal-status">Starting…</p>
    {/if}
    {#if reindexError}
      <div class="ray-alert error" role="alert">
        <span class="alert-icon">!</span>
        {reindexError}
      </div>
    {/if}
  </div>
  {#snippet footer()}
    <button class="ray-btn danger" onclick={cancelReindex} type="button">
      {t('reindex.modal_cancel', lang)}
    </button>
  {/snippet}
</Modal>

<style>
  /* ─── Raycast Design System: Light / Dark via .dark ─── */
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
    --ray-code-bg: rgba(0, 0, 0, 0.04);
    --ray-code-border: rgba(0, 0, 0, 0.06);
    --ray-thumb: #1d1d1f;
    --ray-range-track: rgba(0, 0, 0, 0.1);
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
    --ray-shadow-btn: rgba(0, 0, 0, 0.03);
    --ray-red: #ff6363;
    --ray-green: #5fc992;
    --ray-blue: hsl(202, 100%, 67%);
    --ray-code-bg: rgba(255, 255, 255, 0.04);
    --ray-code-border: rgba(255, 255, 255, 0.06);
    --ray-thumb: #f9f9f9;
    --ray-range-track: rgba(255, 255, 255, 0.1);
    --ray-overlay: #1b1c1e;
  }

  .settings-page {
    padding: 32px 48px;
    max-width: 900px;
    color: var(--ray-text);
    margin: 0 auto;
  }

  /* ─── Header ─── */
  .settings-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 40px;
  }
  .settings-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 28px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--ray-text);
  }
  .settings-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary);
    margin: 4px 0 0;
  }
  .saved-badge {
    background: color-mix(in srgb, var(--ray-green) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--ray-green) 20%, transparent);
    border-radius: 86px;
    padding: 6px 16px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-green);
    letter-spacing: 0.2px;
  }

  /* ─── Loading ─── */
  .loading-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 80px 0;
  }

  /* ─── Tabs ─── */
  .settings-layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 24px;
    align-items: start;
  }
  .settings-tabs {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    padding: 4px;
    position: sticky;
    top: 16px;
  }
  .settings-tab {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    width: 100%;
    text-align: left;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .settings-tab:hover {
    color: var(--ray-text);
    opacity: 0.8;
  }
  .settings-tab.active {
    background: var(--ray-surface-raised);
    color: var(--ray-text);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .tab-icon {
    font-size: 16px;
  }
  .tab-label {
    font-size: 14px;
  }

  /* ─── Sections ─── */
  .section-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 20px;
    font-weight: 500;
    letter-spacing: 0.2px;
    color: var(--ray-text);
    margin: 0 0 16px;
  }
  .settings-section {
    margin-bottom: 40px;
  }

  /* ─── Raycast Card overrides ─── */
  .ray-card {
    padding: 24px;
    gap: 20px;
  }

  /* ─── Provider Grid ─── */
  .provider-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }
  .provider-btn {
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
  }
  .provider-btn:hover {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
  }
  .provider-btn.selected {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .provider-icon {
    font-size: 22px;
  }
  .provider-name {
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .provider-btn.selected .provider-name {
    color: var(--ray-text);
  }

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
  .field-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    margin: 2px 0 0;
  }

  /* ─── Range ─── */
  .range-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .ray-range {
    flex: 1;
    appearance: none;
    height: 4px;
    border-radius: 2px;
    background: var(--ray-range-track);
    outline: none;
    cursor: pointer;
  }
  .ray-range::-webkit-slider-thumb {
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--ray-thumb);
    border: none;
    cursor: pointer;
    box-shadow:
      color-mix(in srgb, var(--ray-text) 10%, transparent) 0px 1px 0px inset,
      color-mix(in srgb, #000 30%, transparent) 0px 1px 3px;
  }
  .range-value {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    border: 1px solid var(--ray-border);
    border-radius: 6px;
    padding: 4px 10px;
    min-width: 48px;
    text-align: center;
  }

  /* ─── Two Column ─── */
  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  /* ─── Actions ─── */
  .action-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 4px;
    flex-wrap: wrap;
  }

  .btn-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid color-mix(in srgb, var(--ray-text) 20%, transparent);
    border-top-color: var(--ray-text);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .inline-badge {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.2px;
    padding: 4px 12px;
    border-radius: 86px;
  }
  .inline-badge.success {
    background: color-mix(in srgb, var(--ray-green) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--ray-green) 20%, transparent);
    color: var(--ray-green);
  }

  /* ─── Alert ─── */
  .ray-alert {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 8px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.2px;
  }
  .ray-alert.error {
    background: color-mix(in srgb, var(--ray-red) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--ray-red) 15%, transparent);
    color: var(--ray-red);
  }
  .alert-icon {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: color-mix(in srgb, var(--ray-red) 15%, transparent);
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
  }

  /* ─── Theme Grid ─── */
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .theme-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 20px 12px;
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .theme-btn:hover {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
  }
  .theme-btn.selected {
    border-color: var(--ray-border-strong);
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .theme-icon {
    font-size: 24px;
  }
  .theme-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .theme-btn.selected .theme-name {
    color: var(--ray-text);
  }
  .theme-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    margin: 0;
  }

  /* ─── Config List ─── */
  .config-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .config-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0;
    border-bottom: 1px solid var(--ray-border-subtle);
    gap: 12px;
  }
  .config-row:last-child {
    border-bottom: none;
  }
  .config-key {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    white-space: nowrap;
  }
  .config-val {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
    flex-shrink: 0;
  }
  .config-val .green {
    color: var(--ray-green);
  }
  .config-val .red {
    color: var(--ray-red);
  }
  .config-code {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 12px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    background: var(--ray-code-bg);
    border: 1px solid var(--ray-code-border);
    border-radius: 6px;
    padding: 4px 10px;
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
  }
  .status-dot.green {
    background: var(--ray-green);
    box-shadow: 0 0 6px color-mix(in srgb, var(--ray-green) 40%, transparent);
  }
  .status-dot.red {
    background: var(--ray-red);
    box-shadow: 0 0 6px color-mix(in srgb, var(--ray-red) 40%, transparent);
  }

  /* Dev-mode environment badge — pill next to the value in the
     Environment row. Only renders when ENVIRONMENT=development. */
  .env-badge {
    display: inline-flex;
    align-items: center;
    margin-left: 8px;
    padding: 2px 8px;
    border-radius: 999px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #fff;
    /* Orange/red gradient so the dev pill is impossible to miss
       when skimming the System section. */
    background: linear-gradient(135deg, #f59e0b, #ef4444);
    box-shadow: 0 0 8px color-mix(in srgb, #f59e0b 30%, transparent);
  }
  /* Secondary text next to a config value — used to show the raw
     DEBUG env var so the user can tell "unset" from "explicitly
     true" at a glance. */
  .config-meta {
    margin-left: 8px;
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 10px;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
  }

  /* ─── Override inner Input/Select elements ─── */
  :global(.settings-page .input),
  :global(.settings-page .select) {
    background: var(--ray-bg, #07080a) !important;
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.08)) !important;
    border-radius: 8px !important;
    color: var(--ray-text, #f9f9f9) !important;
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    letter-spacing: 0.2px;
    box-shadow: none !important;
    transition: border-color 0.15s ease !important;
    width: 100%;
  }
  :global(.settings-page .input:focus),
  :global(.settings-page .select:focus) {
    border-color: var(--ray-blue, hsl(202, 100%, 67%)) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent) !important;
  }
  :global(.settings-page .select) {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9c9d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px !important;
  }
  :global(.settings-page .input::placeholder) {
    color: var(--ray-text-tertiary, #6a6b6c);
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .settings-page {
      padding: 20px 16px;
    }
    .settings-layout {
      grid-template-columns: 1fr;
    }
    .settings-tabs {
      position: static;
      flex-direction: row;
      flex-wrap: wrap;
    }
    .settings-tab {
      width: auto;
      flex: 1 1 calc(50% - 4px);
      justify-content: center;
    }
    .provider-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .two-col {
      grid-template-columns: 1fr;
    }
    .theme-grid {
      grid-template-columns: repeat(3, 1fr);
    }
    .config-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
    }
    .config-code {
      max-width: 100%;
    }
  }

  /* ─── Save All bar ─── */
  .settings-save-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    z-index: 10;
  }
  .settings-save-status {
    flex: 1;
    font-size: 13px;
  }
  .settings-save-ok {
    color: var(--ray-success, #2ecc71);
  }
  .settings-save-fail {
    color: var(--ray-error, #e74c3c);
  }
  .section-hint {
    color: var(--ray-text-muted, #8b8d91);
    font-size: 13px;
    margin: 0 0 6px 0;
  }

  /* ─── Summarization ─── */
  .section-divider {
    border: none;
    border-top: 1px solid var(--ray-border, #2e2f30);
    margin: 20px 0;
  }
  .subsection-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--ray-text-secondary, #98989a);
    margin: 0 0 12px 0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  .toggle-row .field-label {
    margin-bottom: 2px;
  }
  .toggle-row .field-hint {
    margin: 0;
  }

  /* RAG section */
  .rag-status-badge {
    display: inline-flex;
    align-items: center;
    align-self: flex-start;
    padding: 3px 10px;
    border-radius: 999px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    margin-top: 4px;
    transition: all 0.2s ease;
  }
  .rag-status-active {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 18%, transparent);
    color: var(--ray-accent, #8b5cf6);
    border: 1px solid color-mix(in srgb, var(--ray-accent, #8b5cf6) 40%, transparent);
  }
  .rag-status-disabled {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 6%, transparent);
    color: var(--ray-text-tertiary, #6a6b6c);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
  }
  .rag-model-label {
    margin-top: 14px;
  }
  .rag-test-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 12px;
  }
  .rag-test-result {
    font-size: 13px;
  }
  .rag-test-ok {
    color: var(--ray-success, #2ecc71);
  }
  .rag-test-fail {
    color: var(--ray-error, #e74c3c);
  }
  .rag-multilingual-hint {
    font-style: italic;
    opacity: 0.7;
    margin-top: 6px;
  }

  /* ─── Reindex banner & modal ─── */
  .reindex-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    background: color-mix(in srgb, #f5a524 14%, transparent);
    border: 1px solid color-mix(in srgb, #f5a524 35%, transparent);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 0 0 12px;
    width: 100%;
  }
  .reindex-banner-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .reindex-banner strong {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--ray-text, #f9f9f9);
  }
  .reindex-banner p {
    margin: 0;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    color: var(--ray-text-secondary, #9c9c9d);
  }
  .reindex-modal-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .reindex-modal-bot {
    margin: 0;
    font-weight: 600;
    color: var(--ray-text, #f9f9f9);
  }
  .reindex-modal-progress {
    width: 100%;
    height: 8px;
  }
  .reindex-modal-count {
    margin: 0;
    font-size: 12px;
    color: var(--ray-text-tertiary, #6a6b6c);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .reindex-modal-status {
    margin: 0;
    font-size: 12px;
    color: var(--ray-text-secondary, #9c9c9d);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
</style>
