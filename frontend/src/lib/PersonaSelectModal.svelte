<script lang="ts">
  import { scale } from 'svelte/transition';

  import { api, API_BASE, type Persona } from './api';
  import { t } from './i18n';

  const {
    botId = 0,
    lang = 'en',
    mode = 'chat',
    onclose,
    onselect,
    personas = [] as Persona[],
    show = false,
  }: {
    botId?: number;
    lang?: string;
    mode?: 'chat' | 'import';
    onclose?: () => void;
    onselect?: (threadId: number) => void;
    personas?: Persona[];
    show?: boolean;
  } = $props();

  let selectedPersonaId = $state<null | number>(null);
  let creating = $state(false);

  // Create persona mode
  let showCreate = $state(false);
  let newName = $state('');

  // Tooltip state
  let tooltipVisible = $state(false);
  let tooltipText = $state('');
  let tooltipStyle = $state('');
  let tooltipEl: HTMLDivElement | undefined = $state();
  let triggerRect = $state<DOMRect | null>(null);

  function personaAvatarUrl(path: null | string): null | string {
    if (!path) return null;
    return `${API_BASE}${path}`;
  }

  function showTooltip(e: MouseEvent, text: string) {
    tooltipText = text;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    triggerRect = rect;
    // tooltipVisible = true;
  }

  function hideTooltip() {
    tooltipVisible = false;
    triggerRect = null;
  }

  $effect(() => {
    if (!tooltipVisible || !tooltipEl || !triggerRect) return;
    const tr = triggerRect;
    requestAnimationFrame(() => {
      if (!tooltipEl || !tr) return;
      const tw = tooltipEl.offsetWidth;
      const th = tooltipEl.offsetHeight;
      let left = tr.left + tr.width / 2 - tw / 2;
      let top = tr.top - th - 8;
      if (left < 8) left = 8;
      if (left + tw > window.innerWidth - 8) left = window.innerWidth - tw - 8;
      if (top < 8) top = tr.bottom + 8;
      tooltipStyle = `left: ${left}px; top: ${top}px;`;
    });
  });

  function openCreate() {
    showCreate = true;
    selectedPersonaId = null;
  }

  async function doCreate() {
    if (!newName.trim()) return;
    creating = true;
    try {
      const result = await api.createPersona({ name: newName.trim() });
      const created = await api.getPersona(result.id);
      selectedPersonaId = created.id;
      showCreate = false;
      newName = '';
    } catch (e) {
      console.error('Failed to create persona:', e);
    } finally {
      creating = false;
    }
  }

  async function startChat() {
    if (!selectedPersonaId || !botId) return;
    creating = true;
    try {
      if (mode === 'import') {
        onselect?.(selectedPersonaId);
      } else {
        const result = await api.createThread(botId, selectedPersonaId);
        onselect?.(result.id);
      }
    } catch (e) {
      console.error('Failed to start:', e);
    } finally {
      creating = false;
    }
  }
</script>

{#if show}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="psm-overlay" onclick={onclose} role="presentation">
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      transition:scale={{ duration: 200, start: 0.95 }}
      class="psm-modal"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 class="psm-title">
        {mode === 'import' ? t('bot_preview.import_chat', lang) : t('thread.new_chat_title', lang)}
      </h3>
      <p class="psm-hint">
        {mode === 'import'
          ? t('bot_preview.import_select_file', lang)
          : t('thread.new_chat_hint', lang)}
      </p>

      {#if showCreate}
        <!-- Create persona form -->
        <div class="psm-create">
          <input
            bind:value={newName}
            placeholder={t('bot_preview.new_persona_placeholder', lang)}
            onkeydown={(e) => {
              if (e.key === 'Enter') doCreate();
            }}
            class="psm-input"
          />
          <div class="psm-create-actions">
            <button class="psm-btn" onclick={() => (showCreate = false)}
              >{t('thread.cancel', lang)}</button
            >
            <button
              class="psm-btn primary"
              onclick={doCreate}
              disabled={!newName.trim() || creating}
            >
              {t('bot_preview.create', lang)}
            </button>
          </div>
        </div>
      {:else}
        <!-- Persona list -->
        {#if personas.length === 0}
          <div class="psm-empty">
            <p>{t('bot_preview.no_personas', lang)}</p>
          </div>
        {:else}
          <div class="psm-list">
            {#each personas as persona (persona.id)}
              <button
                onclick={() => (selectedPersonaId = persona.id)}
                class="psm-persona"
                class:selected={selectedPersonaId === persona.id}
              >
                <div class="psm-p-avatar">
                  {#if persona.avatar_path}
                    <img
                      src={personaAvatarUrl(persona.avatar_path)}
                      alt={persona.name}
                      class="psm-p-img"
                    />
                  {:else}
                    <div class="psm-p-placeholder">{persona.name.charAt(0).toUpperCase()}</div>
                  {/if}
                </div>
                <div class="psm-p-info">
                  <p class="psm-p-name">{persona.name}</p>
                  {#if persona.description}
                    <p
                      class="psm-p-desc"
                      onmouseenter={(e) => showTooltip(e, persona.description)}
                      onmouseleave={hideTooltip}
                    >
                      {persona.description}
                    </p>
                  {/if}
                </div>
                {#if selectedPersonaId === persona.id}
                  <svg class="psm-check" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fill-rule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clip-rule="evenodd"
                    />
                  </svg>
                {/if}
              </button>
            {/each}
          </div>
        {/if}

        <!-- Actions -->
        <div class="psm-actions">
          <button class="psm-create-btn" onclick={openCreate}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"
              ></line></svg
            >
            {t('bot_preview.create_persona', lang)}
          </button>
          <div class="psm-action-row">
            <button class="psm-btn" onclick={onclose}>{t('thread.cancel', lang)}</button>
            <button
              class="psm-btn primary"
              onclick={startChat}
              disabled={!selectedPersonaId || creating}
            >
              {#if creating}
                <span class="psm-spinner"></span>
              {/if}
              {mode === 'import' ? t('bot_preview.import_chat', lang) : t('thread.start', lang)}
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<!-- Tooltip -->
{#if tooltipVisible}
  <div bind:this={tooltipEl} class="psm-tooltip" style={tooltipStyle}>{tooltipText}</div>
{/if}

<style>
  :root {
    --psm-overlay: rgba(0, 0, 0, 0.45);
    --psm-bg: #ffffff;
    --psm-border: rgba(0, 0, 0, 0.06);
    --psm-text: #1d1d1f;
    --psm-text-secondary: #6e6e73;
    --psm-text-tertiary: #86868b;
    --psm-hover: rgba(0, 0, 0, 0.04);
    --psm-selected: rgba(99, 102, 241, 0.1);
    --psm-selected-border: rgba(99, 102, 241, 0.3);
    --psm-blue: hsl(211, 100%, 50%);
    --psm-tooltip-bg: rgba(30, 30, 32, 0.95);
  }
  :root.dark {
    --psm-overlay: rgba(0, 0, 0, 0.6);
    --psm-bg: #1b1c1e;
    --psm-border: rgba(255, 255, 255, 0.06);
    --psm-text: #f9f9f9;
    --psm-text-secondary: #9c9c9d;
    --psm-text-tertiary: #6a6b6c;
    --psm-hover: rgba(255, 255, 255, 0.04);
    --psm-selected: rgba(99, 102, 241, 0.15);
    --psm-selected-border: rgba(99, 102, 241, 0.35);
    --psm-blue: hsl(202, 100%, 67%);
    --psm-tooltip-bg: rgba(30, 30, 32, 0.95);
  }

  .psm-overlay {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: var(--psm-overlay);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .psm-modal {
    background: var(--psm-bg);
    border: 1px solid var(--psm-border);
    border-radius: 14px;
    padding: 24px;
    max-width: 400px;
    width: calc(100% - 32px);
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.3);
  }
  .psm-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: var(--psm-text);
    margin: 0 0 4px;
    letter-spacing: 0.2px;
  }
  .psm-hint {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    color: var(--psm-text-secondary);
    margin: 0 0 16px;
    letter-spacing: 0.2px;
  }

  /* ─── Create form ─── */
  .psm-create {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .psm-input {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--psm-border);
    border-radius: 8px;
    background: var(--psm-bg);
    color: var(--psm-text);
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    outline: none;
    transition: border-color 0.15s ease;
    box-sizing: border-box;
  }
  .psm-input:focus {
    border-color: var(--psm-blue);
  }
  .psm-input::placeholder {
    color: var(--psm-text-tertiary);
  }
  .psm-create-actions {
    display: flex;
    gap: 8px;
  }

  /* ─── Persona list ─── */
  .psm-empty {
    text-align: center;
    padding: 24px 0;
    color: var(--psm-text-tertiary);
    font-size: 14px;
    font-family: 'Maple Mono', sans-serif;
  }
  .psm-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 240px;
    overflow-y: auto;
    margin-bottom: 16px;
  }
  .psm-persona {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 12px;
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
    transition: all 0.12s ease;
    text-align: left;
  }
  .psm-persona:hover {
    background: var(--psm-hover);
    border-color: var(--psm-border);
  }
  .psm-persona.selected {
    background: var(--psm-selected);
    border-color: var(--psm-selected-border);
  }
  .psm-p-avatar {
    flex-shrink: 0;
  }
  .psm-p-img {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    object-fit: cover;
  }
  .psm-p-placeholder {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    background: linear-gradient(135deg, #8b5cf6, #06b6d4);
  }
  .psm-p-info {
    flex: 1;
    min-width: 0;
  }
  .psm-p-name {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--psm-text);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .psm-p-desc {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--psm-text-tertiary);
    margin: 2px 0 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .psm-check {
    width: 18px;
    height: 18px;
    color: var(--psm-blue);
    flex-shrink: 0;
  }

  /* ─── Actions ─── */
  .psm-actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .psm-create-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 9px;
    border: 1px dashed var(--psm-border);
    border-radius: 10px;
    background: transparent;
    color: var(--psm-text-secondary);
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .psm-create-btn:hover {
    border-color: var(--psm-border);
    background: var(--psm-hover);
    color: var(--psm-text);
  }
  .psm-action-row {
    display: flex;
    gap: 8px;
  }
  .psm-btn {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    border-radius: 86px;
    background: transparent;
    color: var(--psm-text);
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: opacity 0.15s ease;
    border: 1px solid var(--psm-border);
  }
  .psm-btn:hover {
    opacity: 0.7;
  }
  .psm-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .psm-btn.primary {
    background: color-mix(in srgb, var(--psm-text) 8%, transparent);
  }
  .psm-btn.primary:hover {
    opacity: 0.8;
  }
  .psm-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid color-mix(in srgb, var(--psm-text) 20%, transparent);
    border-top-color: var(--psm-text);
    border-radius: 50%;
    animation: psm-spin 0.6s linear infinite;
  }
  @keyframes psm-spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ─── Tooltip ─── */
  .psm-tooltip {
    position: fixed;
    z-index: 100;
    padding: 6px 12px;
    border-radius: 6px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 500;
    line-height: 1.4;
    letter-spacing: 0.2px;
    color: #fff;
    background: var(--psm-tooltip-bg);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
    pointer-events: none;
    max-width: 240px;
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
