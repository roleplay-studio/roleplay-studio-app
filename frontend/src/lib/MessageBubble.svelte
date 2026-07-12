<script lang="ts">
  import { type Message, type ThreadFileDTO, thumbUrl } from './api';
  import { t } from './i18n';
  import MarkdownRenderer from './MarkdownRenderer.svelte';
  import MessageContextMenu from './MessageContextMenu.svelte';
  import { formatRelativeTime } from './time';
  import ActionButtons from './ui/ActionButtons.svelte';
  import GameStats from './ui/GameStats.svelte';
  import { GeneratedAvatar, Tooltip, TTSButton } from './ui/index';
  import { type MetadataEntry, parseMessageContent } from './utils/parseMetadata';

  const {
    botAvatarPath = null as null | string,
    botName = 'B',
    files = [] as ThreadFileDTO[],
    isLast = false,
    lang = 'en',
    msg,
    onaction,
    ondelete,
    onedit,
    onopendebug,
    onregenerate,
    onretry,
    onswitchversion,
    personaAvatarPath = null as null | string,
    personaName = 'U',
    showRetry = false,
    streaming = false,
    versions = [] as Message[],
  }: {
    botAvatarPath?: null | string;
    botName?: string;
    files?: ThreadFileDTO[];
    isLast?: boolean;
    lang?: string;
    msg: Message;
    onaction?: (text: string) => void;
    ondelete?: (msgId: number) => void;
    onedit?: (m: Message) => void;
    /** Open the dev-mode LLM debug modal for this assistant message.
     *  Only wired up when the parent has debug info for this id. */
    onopendebug?: () => void;
    onregenerate?: () => void;
    onretry?: () => void;
    onswitchversion?: (versionId: number) => void;
    personaAvatarPath?: null | string;
    personaName?: string;
    showRetry?: boolean;
    streaming?: boolean;
    versions?: Message[];
  } = $props();

  function variable_replace(message: string): string {
    message = message.replace('{{user}}', personaName);
    message = message.replace('{{char}}', botName);
    return message;
  }

  const currentVersionIndex = $derived(
    versions.length > 0 ? versions.findIndex((v) => v.is_active) : -1,
  );
  const totalVersions = $derived(versions.length);
  const canGoPrev = $derived(totalVersions > 1 && currentVersionIndex > 0);

  // Reasoning panel — open by default. State is persisted in localStorage
  // so the user's choice (collapsed / expanded) is consistent across
  // reloads and across all reasoning panels in all threads. Default is
  // "true" (open) so reasoning is visible by default per spec.
  const REASONING_OPEN_KEY = 'chatReasoningOpen';
  function readReasoningOpen(): boolean {
    if (typeof localStorage === 'undefined') return true;
    const raw = localStorage.getItem(REASONING_OPEN_KEY);
    // Default: open. Only the explicit string "false" collapses it.
    return raw !== 'false';
  }
  let reasoningOpen = $state(readReasoningOpen());
  // Floating system-prompt panel starts collapsed; world-state opens
  // by default since state is the most useful debug signal. Both stay
  // per-message (no shared localStorage key) — the reasoning pattern
  // uses one global because it's usually small; prompt and state can
  // be longer and vary turn-to-turn, so per-bubble state is simpler.
  let stateOpen = $state(true);
  function onReasoningToggle(e: Event) {
    const el = e.currentTarget as HTMLDetailsElement;
    reasoningOpen = el.open;
    try {
      localStorage.setItem(REASONING_OPEN_KEY, String(el.open));
    } catch {
      // localStorage may be unavailable (private mode, quota); fall back
      // silently — the in-memory state still updates.
    }
  }
  const canGoNext = $derived(totalVersions > 1 && currentVersionIndex < totalVersions - 1);

  // Right-click context menu state. Null = menu closed.
  let menuPos = $state<null | { x: number; y: number }>(null);

  function handleContextMenu(e: MouseEvent) {
    // Don't hijack the browser's native menu on form controls / links.
    const target = e.target as HTMLElement | null;
    if (target?.closest('a, button, input, textarea, [contenteditable]')) {
      return;
    }
    e.preventDefault();
    menuPos = { x: e.clientX, y: e.clientY };
  }

  // Parse message content: strip --- metadata from display
  const parsed = $derived.by(() => {
    const p = parseMessageContent(variable_replace(msg.content));
    return {
      actions: p.actions as null | string[],
      mainContent: p.mainContent,
      stats: p.stats as MetadataEntry[] | null,
    };
  });

  function goPrev() {
    if (canGoPrev && versions[currentVersionIndex - 1]?.id !== undefined) {
      onswitchversion?.(versions[currentVersionIndex - 1].id!);
    }
  }

  function goNext() {
    if (canGoNext && versions[currentVersionIndex + 1]?.id !== undefined) {
      onswitchversion?.(versions[currentVersionIndex + 1].id!);
    }
  }
</script>

{#snippet versionControls()}
  {#if totalVersions > 1}
    <div class="mb-versions">
      <Tooltip text={t('message.previous_version', lang)} position="bottom">
        <button
          class="mb-version-btn"
          disabled={!canGoPrev}
          onclick={goPrev}
          aria-label={t('message.previous_version', lang)}
          type="button"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg
          >
        </button>
      </Tooltip>
      <span class="mb-version-num">{currentVersionIndex + 1}/{totalVersions}</span>
      <Tooltip text={t('message.next_version', lang)} position="bottom">
        <button
          class="mb-version-btn"
          disabled={!canGoNext}
          onclick={goNext}
          aria-label={t('message.next_version', lang)}
          type="button"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg
          >
        </button>
      </Tooltip>
    </div>
  {/if}
{/snippet}

{#if menuPos}
  <MessageContextMenu
    {msg}
    position={menuPos}
    onclose={() => (menuPos = null)}
    onedit={(m) => {
      menuPos = null;
      onedit?.(m);
    }}
  />
{/if}
{#if msg.role === 'assistant'}
  <div class="mb-row mb-assistant">
    <div class="mb-avatar">
      {#if botAvatarPath}
        <img src={thumbUrl(botAvatarPath, 50)} alt={botName} class="mb-avatar-img" />
      {:else}
        <GeneratedAvatar name={botName} size={36} />
      {/if}
    </div>
    <div class="mb-content">
      <div class="mb-bubble bot" oncontextmenu={handleContextMenu} role="presentation">
        {#if msg.reasoning}
          <details class="mb-reasoning" open={reasoningOpen} ontoggle={onReasoningToggle}>
            <summary>
              <span class="mb-reasoning-dot"></span>
              {t('chat.reasoning_label', lang)}
            </summary>
            <div class="mb-reasoning-body">{msg.reasoning}</div>
          </details>
        {/if}

        {#if msg.dynamic_system_prompt}
          <details class="mb-reasoning mb-prompt" open={false}>
            <summary>
              <span class="mb-reasoning-dot"></span>
              {t('chat.dynamic_system_prompt_label', lang)}
            </summary>
            <pre class="mb-reasoning-body">{msg.dynamic_system_prompt}</pre>
          </details>
        {/if}

        {#if msg.state}
          <details class="mb-reasoning mb-state" open={stateOpen}>
            <summary>
              <span class="mb-reasoning-dot"></span>
              {t('chat.world_state_label', lang)}
            </summary>
            <pre class="mb-reasoning-body">{msg.state}</pre>
          </details>
        {/if}

        {#if streaming && !msg.content}
          <div class="mb-typing">
            <span></span><span></span><span></span>
          </div>
        {:else}
          <MarkdownRenderer content={parsed.mainContent} {streaming} {isLast} />
        {/if}

        {#if files.length > 0}
          <div class="mb-files">
            {#each files as file (file.filename)}
              <span class="mb-file-chip">
                {#if file.file_type === 'image'}🖼️{:else if file.file_type === 'pdf'}📄{:else}📎{/if}
                {file.filename}
              </span>
            {/each}
          </div>
        {/if}
        {#if parsed.stats && parsed.stats.length > 0}
          <GameStats entries={parsed.stats} />
        {/if}
        {#if parsed.actions && parsed.actions.length > 0}
          <ActionButtons actions={parsed.actions} {onaction} />
        {/if}
        {#if msg.created_at}
          <time class="mb-time">{formatRelativeTime(msg.created_at, lang)}</time>
        {/if}
        {#if msg.short_content}
          <small class="text-xs opacity-50 ml-6">{msg.short_content}</small>
        {/if}
      </div>
      {#if msg.id !== null}
        <div class="mb-actions">
          {@render versionControls()}
          {#if msg.content}
            <TTSButton content={parsed.mainContent} />
          {/if}
          {#if isLast && msg.role === 'assistant' && onregenerate}
            <Tooltip text={t('message.regenerate', lang)} position="bottom">
              <button
                class="mb-action-btn"
                onclick={() => onregenerate?.()}
                aria-label={t('message.regenerate', lang)}
                type="button"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M3 12a9 9 0 019-9 9.75 9.75 0 016.74 2.74L21 8"></path><path
                    d="M21 3v5h-5"
                  ></path><path d="M21 12a9 9 0 01-9 9 9.75 9.75 0 01-6.74-2.74L3 16"></path><path
                    d="M8 16H3v5"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
          {#if onedit}
            <Tooltip text={t('message.edit', lang)} position="bottom">
              <button
                class="mb-action-btn"
                onclick={() => onedit?.(msg)}
                aria-label={t('message.edit', lang)}
                type="button"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path><path
                    d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
          {#if onopendebug}
            <Tooltip text={t('message.debug', lang)} position="bottom">
              <button
                class="mb-action-btn mb-debug"
                onclick={() => onopendebug?.()}
                aria-label={t('message.debug', lang)}
                type="button"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path
                    d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
          {#if msg.id !== null && ondelete}
            <Tooltip text={t('message.delete', lang)} position="bottom">
              <button
                class="mb-action-btn danger"
                onclick={() => ondelete?.(msg.id!)}
                aria-label={t('message.delete', lang)}
                type="button"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><polyline points="3 6 5 6 21 6"></polyline><path
                    d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{:else}
  <div class="mb-row mb-user">
    <div class="mb-content mb-user-content">
      <div class="mb-bubble user" oncontextmenu={handleContextMenu} role="presentation">
        <MarkdownRenderer content={parsed.mainContent} />
        {#if files.length > 0}
          <div class="mb-files justify-end">
            {#each files as file (file.filename)}
              <span class="mb-file-chip user">
                {#if file.file_type === 'image'}🖼️{:else if file.file_type === 'pdf'}📄{:else}📎{/if}
                {file.filename}
              </span>
            {/each}
          </div>
        {/if}
        {#if msg.created_at}
          <p class="mb-time">{formatRelativeTime(msg.created_at, lang)}</p>
        {/if}
      </div>

      {#if msg.id !== null}
        <div class="mb-actions mb-actions-right">
          {#if showRetry && onretry}
            <Tooltip text={t('message.retry', lang)} position="bottom">
              <button class="mb-action-btn mb-retry" onclick={onretry}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M3 12a9 9 0 019-9 9.75 9.75 0 016.74 2.74L21 8" /><path
                    d="M21 3v5h-5"
                  /><path d="M21 12a9 9 0 01-9 9 9.75 9.75 0 01-6.74-2.74L3 16" /><path
                    d="M8 16H3v5"
                  /></svg
                >
              </button>
            </Tooltip>
          {/if}

          {@render versionControls()}
          {#if onedit}
            <Tooltip text={t('message.edit', lang)} position="bottom">
              <button class="mb-action-btn" onclick={() => onedit?.(msg)}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path><path
                    d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
          {#if msg.id !== null && ondelete}
            <Tooltip text={t('message.delete', lang)} position="bottom">
              <button class="mb-action-btn danger" onclick={() => ondelete?.(msg.id!)}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><polyline points="3 6 5 6 21 6"></polyline><path
                    d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
                  ></path></svg
                >
              </button>
            </Tooltip>
          {/if}
        </div>
      {/if}
    </div>
    <div class="mb-avatar">
      {#if personaAvatarPath}
        <img src={thumbUrl(personaAvatarPath, 50)} alt="" class="mb-avatar-img" />
      {:else}
        <GeneratedAvatar name={personaName} size={36} />
      {/if}
    </div>
  </div>
{/if}

<style>
  :root {
    --mb-bot-bg: #f0f0f2;
    --mb-bot-border: rgba(0, 0, 0, 0.06);
    --mb-user-bg: rgba(99, 102, 241, 0.1);
    --mb-user-border: rgba(99, 102, 241, 0.2);
    --mb-text: #1d1d1f;
    --mb-text-secondary: #6e6e73;
    --mb-text-tertiary: #86868b;
    --mb-hover: rgba(0, 0, 0, 0.04);
    --mb-red: #ff3b30;
  }
  :root.dark {
    --mb-bot-bg: rgba(255, 255, 255, 0.04);
    --mb-bot-border: rgba(255, 255, 255, 0.06);
    --mb-user-bg: rgba(99, 102, 241, 0.12);
    --mb-user-border: rgba(99, 102, 241, 0.25);
    --mb-text: #f9f9f9;
    --mb-text-secondary: #9c9c9d;
    --mb-text-tertiary: #6a6b6c;
    --mb-hover: rgba(255, 255, 255, 0.04);
    --mb-red: #ff6363;
  }

  .mb-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }

  .mb-user {
    justify-content: flex-end;
  }

  /* ─── Avatar ─── */
  .mb-avatar {
    flex-shrink: 0;
  }
  .mb-avatar-img {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    object-fit: cover;
  }
  /* ─── Content ─── */
  .mb-content {
    flex: 1;
    min-width: 0;
    max-width: 75%;
  }
  .mb-user-content {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .mb-bubble {
    padding: 12px 16px;
    border-radius: 14px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    letter-spacing: 0.15px;
  }
  .mb-bubble.bot {
    background: var(--mb-bot-bg);
    border: 1px solid var(--mb-bot-border);
    color: var(--mb-text);
    border-bottom-left-radius: 4px;
  }
  .mb-bubble.user {
    background: var(--mb-user-bg);
    border: 1px solid var(--mb-user-border);
    color: var(--mb-text);
    border-bottom-right-radius: 4px;
  }

  .mb-time {
    font-family: 'Maple Mono', sans-serif;
    font-size: 10px;
    font-weight: 400;
    color: var(--mb-text-tertiary);
    margin: 6px 0 0;
    letter-spacing: 0.2px;
  }

  /* ─── Typing ─── */
  .mb-typing {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 0;
  }
  .mb-typing span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--mb-text-tertiary);
    animation: mb-blink 1.4s infinite both;
  }
  .mb-typing span:nth-child(2) {
    animation-delay: 0.2s;
  }
  .mb-typing span:nth-child(3) {
    animation-delay: 0.4s;
  }
  @keyframes mb-blink {
    0%,
    100% {
      opacity: 0.2;
    }
    20% {
      opacity: 1;
    }
  }

  /* ─── Files ─── */
  .mb-files {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
  }
  .mb-file-chip {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 6px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 500;
    background: color-mix(in srgb, var(--mb-text) 6%, transparent);
    color: var(--mb-text-secondary);
  }
  .mb-file-chip.user {
    background: rgba(99, 102, 241, 0.12);
    color: #818cf8;
  }

  /* ─── Actions ─── */
  .mb-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    margin-top: 4px;
    opacity: 0;
    transition: opacity 0.12s ease;
  }
  .mb-content:hover .mb-actions {
    opacity: 1;
  }
  .mb-actions-right {
    justify-content: flex-end;
  }

  .mb-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--mb-text-tertiary);
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .mb-action-btn:hover {
    background: var(--mb-hover);
    color: var(--mb-text);
  }
  .mb-action-btn.danger:hover {
    background: color-mix(in srgb, var(--mb-red) 10%, transparent);
    color: var(--mb-red);
  }
  /*.mb-action-btn.mb-debug {
    color: #6366f1;
  }*/
  .mb-action-btn.mb-debug:hover {
    background: color-mix(in srgb, #6366f1 10%, transparent);
    /*color: #4f46e5;*/
  }
  .mb-retry {
    color: #f59e0b;
  }
  .mb-retry:hover {
    background: color-mix(in srgb, #f59e0b 10%, transparent);
    color: #fbbf24;
  }

  .mb-versions {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    border-radius: 6px;
    border: 1px solid var(--mb-bot-border);
    background: transparent;
  }
  .mb-version-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--mb-text-tertiary);
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .mb-version-btn:hover {
    background: var(--mb-hover);
    color: var(--mb-text);
  }
  .mb-version-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
  .mb-version-num {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 10px;
    font-weight: 500;
    color: var(--mb-text-tertiary);
    min-width: 28px;
    text-align: center;
  }

  /* Reasoning (chain-of-thought) — collapsed by default to keep the
     chat tidy. The dot pulses while the model is still thinking. */
  .mb-reasoning {
    margin-top: 10px;
    border: 1px solid var(--mb-border);
    border-radius: 8px;
    background: color-mix(in srgb, var(--mb-text) 3%, transparent);
    overflow: hidden;
  }
  .mb-reasoning > summary {
    list-style: none;
    cursor: pointer;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    color: var(--mb-text-tertiary);
    user-select: none;
  }
  .mb-reasoning > summary::-webkit-details-marker {
    display: none;
  }
  .mb-reasoning > summary:hover {
    color: var(--mb-text-secondary);
  }
  .mb-reasoning-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--mb-accent, #8b5cf6);
    opacity: 0.7;
  }
  .mb-reasoning-body {
    padding: 4px 12px 12px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    line-height: 1.55;
    color: var(--mb-text-secondary);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 320px;
    overflow-y: auto;
  }

  /* Floating system-prompt panel: tinted summary + dot so the
     operator can tell it apart from reasoning/world-state at a
     glance. Uses the mb-accent token so it reads as "instruction
     sent to the model". */
  .mb-prompt > summary {
    color: var(--mb-accent, #8b5cf6);
  }
  .mb-prompt > summary > .mb-reasoning-dot {
    background: var(--mb-accent, #8b5cf6);
  }

  /* World-state panel: a second accent color, distinct from prompt
     and reasoning, so three panels on one bubble stay readable. The
     fallback value matches Raycast's ``--ray-info`` if the app
     doesn't override it. */
  .mb-state > summary {
    color: var(--mb-info, #3b82f6);
  }
  .mb-state > summary > .mb-reasoning-dot {
    background: var(--mb-info, #3b82f6);
  }
</style>
