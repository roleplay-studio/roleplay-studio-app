<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, API_BASE, type Bot, type Persona, type Thread } from '../api';
  import { currentLang, t } from '../i18n';
  import PersonaSelectModal from '../PersonaSelectModal.svelte';
  import ThreadTree from '../ThreadTree.svelte';
  import { GeneratedAvatar, Loading } from '../ui';

  const { botId = '0' }: { botId?: string } = $props();

  let lang = $state('en');
  let bot: Bot | null = $state(null);
  let loading = $state(true);
  let showPersonaModal = $state(false);
  let recentThreads: Thread[] = $state([]);
  let unsubLang: (() => void) | undefined;

  // Import state
  let importing = $state(false);
  let importPersonaId: null | number = $state(null);
  let fileInput: HTMLInputElement | undefined = $state();
  let importError = $state('');
  let importLoading = $state(false);

  function avatarUrl(path: null | string): null | string {
    if (!path) return null;
    return `${API_BASE}${path}`;
  }

  let personas: Persona[] = $state([]);

  onMount(async () => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    try {
      const id = parseInt(botId);
      if (id) {
        const [b, personaList, threads] = await Promise.all([
          api.getBot(id),
          api.listPersonas(),
          api.listBotThreads(id),
        ]);
        bot = b;
        personas = personaList;
        recentThreads = threads;
      }
    } catch (e) {
      console.error('Failed to load bot:', e);
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    unsubLang?.();
  });

  function goBack() {
    window.location.hash = '#/';
  }

  function onNewThread(threadId: number) {
    showPersonaModal = false;
    window.location.hash = `/chat?bot=${bot!.id}&thread=${threadId}`;
  }

  function openThread(threadId: number) {
    window.location.hash = `/chat?bot=${bot!.id}&thread=${threadId}`;
  }

  // ── Import chat ──

  function startImport() {
    importing = true;
    importError = '';
    showPersonaModal = true;
  }

  function onImportPersonaSelected(personaId: number) {
    importPersonaId = personaId;
    showPersonaModal = false;
    setTimeout(() => fileInput?.click(), 150);
  }

  async function onFilePicked(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file || !bot) return;

    importLoading = true;
    importError = '';
    try {
      const result = await api.importChat(bot.id, file, importPersonaId);
      // Redirect after brief delay
      setTimeout(() => {
        window.location.hash = `/chat?bot=${bot!.id}&thread=${result.thread_id}`;
      }, 600);
    } catch (e: any) {
      importError = e?.detail || e?.message || t('bot_preview.import_failed', lang);
    } finally {
      importLoading = false;
      importing = false;
      target.value = '';
    }
  }
</script>

<div class="bp-page">
  {#if loading}
    <div class="bp-loading"><Loading size="lg" /></div>
  {:else if !bot}
    <div class="bp-notfound">
      <p>{t('bot_preview.not_found', lang)}</p>
      <button class="bp-back-link" onclick={goBack}>← {t('bot_preview.back', lang)}</button>
    </div>
  {:else}
    <!-- Hero -->
    <div class="bp-hero">
      {#if bot.avatar_path}
        <img src={avatarUrl(bot.avatar_path)} alt={bot.name} class="bp-hero-img" />
      {:else}
        <div class="bp-hero-placeholder">
          <GeneratedAvatar name={bot.name} shape="square" block />
        </div>
      {/if}
      <div class="bp-hero-overlay"></div>

      <!-- Back button -->
      <button class="bp-back-btn" onclick={goBack}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg
        >
      </button>

      <!-- Hero content -->
      <div class="bp-hero-content">
        <div class="bp-hero-cats">
          {#each bot.categories as cat (cat)}
            <span class="bp-hero-cat">{cat}</span>
          {/each}
          <span
            class="bp-hero-type"
            class:rp={bot.bot_type === 'rp'}
            class:assistant={bot.bot_type === 'assistant'}
            class:agent={bot.bot_type === 'agent'}
          >
            {bot.bot_type === 'assistant' ? 'Assistant' : bot.bot_type === 'agent' ? 'Agent' : 'RP'}
          </span>
        </div>
        <h1 class="bp-hero-name">{bot.name}</h1>
      </div>
    </div>

    <!-- Two-column content -->
    <div class="bp-layout">
      <!-- Left column -->
      <div class="bp-left">
        <!-- Description -->
        {#if bot.description}
          <div class="bp-card">
            <p class="bp-desc-text">{bot.description}</p>
          </div>
        {/if}
        <!-- Start Chat -->
        <button class="bp-start-btn" onclick={() => (showPersonaModal = true)}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path></svg
          >
          {t('bot_preview.start_chat', lang)}
        </button>

        <!-- Import Chat -->
        {#if importError}
          <div class="bp-import-error">{importError}</div>
        {/if}
        <button
          class="bp-start-btn"
          class:bp-import-loading={importLoading}
          style="background: color-mix(in srgb, var(--bp-text) 5%, transparent); color: var(--bp-text);"
          onclick={startImport}
          disabled={importLoading}
        >
          {#if importLoading}
            <Loading size="sm" />
          {:else}
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline
                points="17 8 12 3 7 8"
              ></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg
            >
          {/if}
          {t('bot_preview.import_chat', lang)}
        </button>
        <input
          type="file"
          accept=".json"
          class="hidden"
          bind:this={fileInput}
          onchange={onFilePicked}
        />
      </div>

      <!-- Right column — poster -->
      <div class="bp-right">
        <div
          class="bp-poster hover:scale-110 transform-gpu transition-transform duration-300 ease-in-out"
        >
          {#if bot.avatar_path}
            <img src={avatarUrl(bot.avatar_path)} alt={bot.name} class="bp-poster-img" />
          {:else}
            <div class="bp-poster-placeholder">
              {bot.name.charAt(0).toUpperCase()}
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!-- Recent chats — thread tree (roots + indented forks) -->
    {#if recentThreads.length > 0}
      <div class="bp-recent">
        <h2 class="bp-recent-title">{t('chat.tree.title', lang)}</h2>
        <ThreadTree
          threads={recentThreads}
          onselectThread={(_, threadId) => openThread(threadId)}
          botId={bot?.id ?? 0}
          {lang}
        />
      </div>
    {/if}
  {/if}
</div>

<PersonaSelectModal
  show={showPersonaModal}
  {personas}
  botId={bot?.id ?? 0}
  {lang}
  mode={importing ? 'import' : 'chat'}
  onselect={importing ? onImportPersonaSelected : onNewThread}
  onclose={() => {
    showPersonaModal = false;
    importing = false;
  }}
/>

<style>
  /* ── CSS variables — light ── */
  :root {
    --bp-bg: var(--ray-bg, #f5f5f7);
    --bp-bg-card: var(--ray-surface, #ffffff);
    --bp-border: var(--ray-border, rgba(0, 0, 0, 0.06));
    --bp-border-strong: var(--ray-border-strong, rgba(0, 0, 0, 0.1));
    --bp-text: var(--ray-text, #1d1d1f);
    --bp-text-secondary: var(--ray-text-secondary, #6e6e73);
    --bp-text-tertiary: var(--ray-text-tertiary, #86868b);
    --bp-shadow-ring: var(--ray-shadow-ring, rgba(0, 0, 0, 0.04));
    --bp-shadow-inset: var(--ray-shadow-inset, rgba(0, 0, 0, 0.02));
    --bp-blue: var(--ray-blue, hsl(211, 100%, 50%));
  }

  .bp-page {
    color: var(--bp-text);
    min-height: 100vh;
  }

  /* ─── Loading / Not found ─── */
  .bp-loading {
    display: flex;
    justify-content: center;
    padding: 80px 0;
  }
  .bp-notfound {
    text-align: center;
    padding: 80px 0;
  }
  .bp-notfound p {
    font-size: 16px;
    color: var(--bp-text-secondary);
    margin-bottom: 8px;
  }
  .bp-back-link {
    background: none;
    border: none;
    color: var(--bp-blue);
    cursor: pointer;
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
  }

  /* ─── Hero ─── */
  .bp-hero {
    position: relative;
    width: 100%;
    height: 280px;
    overflow: hidden;
    background: color-mix(in srgb, var(--bp-text) 3%, transparent);
  }
  .bp-hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top;
  }
  .bp-hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .bp-hero-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 70%;
    background: linear-gradient(to top, var(--bp-bg) 15%, transparent);
    pointer-events: none;
  }
  .bp-back-btn {
    position: absolute;
    top: 20px;
    left: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    background: color-mix(in srgb, var(--bp-bg-card) 60%, transparent);
    backdrop-filter: blur(8px);
    color: #fff;
    cursor: pointer;
    transition: all 0.12s ease;
    z-index: 2;
  }
  .bp-back-btn:hover {
    background: var(--bp-bg-card);
    color: var(--bp-text);
  }

  .bp-hero-content {
    position: absolute;
    bottom: 32px;
    left: 48px;
    right: 48px;
    z-index: 2;
  }
  .bp-hero-cats {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .bp-hero-cat {
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 500;
    padding: 3px 12px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--bp-bg-card) 70%, transparent);
    backdrop-filter: blur(8px);
    color: var(--bp-text);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .bp-hero-type {
    font-family: 'Maple Mono', sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 3px 12px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--bp-bg-card) 70%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .bp-hero-type.rp {
    color: var(--bp-blue);
  }
  .bp-hero-type.assistant {
    color: #5fc992;
  }
  .bp-hero-type.agent {
    color: #f59e0b;
  }
  .bp-hero-name {
    font-family: 'Maple Mono', sans-serif;
    font-size: 32px;
    font-weight: 600;
    color: #fff;
    margin: 0;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    letter-spacing: 0.2px;
  }

  /* ─── Two-column layout ─── */
  .bp-layout {
    max-width: 960px;
    margin: 0 auto;
    padding: 32px 48px 24px;
    display: grid;
    grid-template-columns: 1fr 260px;
    gap: 32px;
    align-items: start;
  }

  .bp-left {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }

  /* ─── Card ─── */
  .bp-card {
    background: var(--bp-bg-card);
    border: 1px solid var(--bp-border);
    border-radius: 12px;
    padding: 20px;
    box-shadow:
      var(--bp-shadow-ring) 0px 0px 0px 1px,
      var(--bp-shadow-inset) 0px 0px 0px 1px inset;
  }
  .bp-section-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: var(--bp-text-tertiary);
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin: 0 0 10px;
  }
  .bp-desc-text {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 400;
    color: var(--bp-text);
    letter-spacing: 0.2px;
    line-height: 1.7;
    margin: 0;
    white-space: pre-wrap;
  }
  .bp-fm {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    color: var(--bp-text-secondary);
  }

  /* ─── Poster (right column) ─── */
  .bp-right {
    position: sticky;
    top: 24px;
  }
  .bp-poster {
    border-radius: 14px;
    overflow: hidden;
    box-shadow:
      var(--bp-shadow-ring) 0px 0px 0px 1px,
      0 8px 32px rgba(0, 0, 0, 0.2);
  }
  .bp-poster-img {
    width: 100%;
    aspect-ratio: 3 / 4;
    object-fit: cover;
    display: block;
  }
  .bp-poster-placeholder {
    width: 100%;
    aspect-ratio: 3 / 4;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 72px;
    font-weight: 700;
    background: linear-gradient(135deg, #8b5cf6, #06b6d4);
    color: #fff;
  }

  /* ─── Start Chat button ─── */
  .bp-start-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 28px;
    border-radius: 86px;
    border: none;
    background: color-mix(in srgb, var(--bp-text) 90%, transparent);
    color: var(--bp-bg);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: opacity 0.15s ease;
    width: 100%;
    margin-top: 4px;
  }
  .bp-start-btn:hover {
    opacity: 0.85;
  }

  /* ─── Import chat ─── */
  .bp-import-error {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    color: #ef4444;
    margin-bottom: 8px;
    text-align: center;
  }
  .bp-import-loading {
    cursor: wait;
    opacity: 0.7;
  }

  /* ─── Recent chats ─── */
  .bp-recent {
    max-width: 960px;
    margin: 0 auto;
    padding: 0 48px 48px;
  }
  .bp-recent-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: var(--bp-text-tertiary);
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin: 0 0 12px;
  }
  .bp-recent-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .bp-recent-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bp-bg-card);
    border: 1px solid var(--bp-border);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.12s ease;
    text-align: left;
    width: 100%;
    box-shadow: var(--bp-shadow-ring) 0px 0px 0px 1px;
  }
  .bp-recent-item:hover {
    border-color: var(--bp-border-strong);
    background: color-mix(in srgb, var(--bp-text) 3%, var(--bp-bg-card));
  }
  .bp-recent-avatar {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    overflow: hidden;
  }
  .bp-recent-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .bp-recent-avatar-ph {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 600;
    background: color-mix(in srgb, var(--bp-text) 8%, transparent);
    color: var(--bp-text-secondary);
  }
  .bp-recent-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .bp-recent-persona {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--bp-text);
    letter-spacing: 0.2px;
  }
  .bp-recent-preview {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    color: var(--bp-text-tertiary);
    letter-spacing: 0.1px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bp-recent-preview.bp-recent-summary {
    color: var(--bp-text);
    font-style: italic;
  }
  .bp-recent-time {
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    color: var(--bp-text-tertiary);
    letter-spacing: 0.1px;
    flex-shrink: 0;
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .bp-hero {
      height: 200px;
    }
    .bp-hero-name {
      font-size: 24px;
    }
    .bp-hero-content {
      left: 20px;
      right: 20px;
      bottom: 20px;
    }
    .bp-layout {
      grid-template-columns: 1fr;
      padding: 20px 16px 24px;
    }
    .bp-right {
      display: none;
    }
    .bp-recent {
      padding: 0 16px 32px;
    }
  }
</style>
