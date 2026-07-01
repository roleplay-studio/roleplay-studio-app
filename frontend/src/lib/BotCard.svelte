<!-- BotCard — Raycast-style bot card, reusable in dashboard/list pages -->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { avatarUrl, type Bot } from './api';
  import { currentLang, t } from './i18n';
  import { GeneratedAvatar } from './ui';

  let lang = $state('en');
  let unsubLang: (() => void) | undefined;

  onMount(() => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
  });

  onDestroy(() => {
    unsubLang?.();
  });

  const {
    bot,
    onchat,
    onclick,
    ondelete,
    onedit,
    onexport,
    showActions = false,
  }: {
    bot: Bot;
    compact?: boolean;
    onchat?: (bot: Bot) => void;
    onclick?: (bot: Bot) => void;
    ondelete?: (bot: Bot) => void;
    onedit?: (bot: Bot) => void;
    onexport?: (bot: Bot, format: 'json' | 'png') => void;
    showActions?: boolean;
  } = $props();

  let exportOpen = $state(false);

  function toggleExport(e: MouseEvent) {
    e.stopPropagation();
    exportOpen = !exportOpen;
  }

  function pickFormat(e: MouseEvent, format: 'json' | 'png') {
    e.stopPropagation();
    exportOpen = false;
    onexport?.(bot, format);
  }

  // The bot card hero uses GeneratedAvatar (from ./ui) as a fullscreen
  // block-mode placeholder (shape="square", block=true) when the bot
  // has no uploaded avatar. The face is rendered at 120px so it's
  // readable across the full hero area.
</script>

<div
  class="bc-card"
  class:bc-clickable={!!onclick}
  role={onclick ? 'button' : undefined}
  tabindex={onclick ? 0 : undefined}
  onclick={() => onclick?.(bot)}
  onkeydown={(e) => e.key === 'Enter' && onclick?.(bot)}
>
  <!-- Hero -->
  <div class="bc-hero">
    {#if bot.avatar_path}
      <img
        src={avatarUrl(bot.avatar_path)}
        alt={bot.name}
        class="bc-hero-img transform-cpu transform-gpu"
      />
    {:else}
      <div class="bc-hero-placeholder">
        <GeneratedAvatar name={bot.name} shape="square" block />
      </div>
    {/if}
    <div class="bc-hero-overlay"></div>

    <!-- Categories -->
    <div class="bc-hero-cats">
      {#each bot.categories as cat (cat)}
        <span class="bc-hero-cat">{cat}</span>
      {/each}
    </div>

    <!-- Type badge -->
    <span
      class="bc-hero-type"
      class:rp={bot.bot_type === 'rp'}
      class:assistant={bot.bot_type === 'assistant'}
      class:agent={bot.bot_type === 'agent'}
    >
      {bot.bot_type === 'assistant' ? 'Assistant' : bot.bot_type === 'agent' ? 'Agent' : 'RP'}
    </span>

    <!-- Name on hero -->
    <h3 class="bc-hero-name">{bot.name}</h3>
  </div>

  <!-- Body -->
  <div class="bc-body">
    <p class="bc-desc">{bot.description || bot.personality}</p>
    <div class="bc-footer">
      <span class="bc-threads">
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path></svg
        >
        {bot.thread_count} чатов
      </span>

      {#if showActions}
        <div class="bc-actions">
          {#if onchat}
            <button
              class="bc-action-btn"
              onclick={(e) => {
                e.stopPropagation();
                onchat(bot);
              }}
              title={t('dashboard.chat', lang)}
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
                ><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path></svg
              >
            </button>
          {/if}
          {#if onedit}
            <button
              class="bc-action-btn"
              onclick={(e) => {
                e.stopPropagation();
                onedit(bot);
              }}
              title={t('common.edit_bot', lang)}
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
          {/if}
          {#if onexport}
            <div class="bc-export-wrap">
              <button class="bc-action-btn" onclick={toggleExport} title={t('common.export', lang)}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><path d="M7 10l5 5 5-5"
                  ></path><path d="M12 15V3"></path></svg
                >
              </button>
              {#if exportOpen}
                <div class="bc-export-menu" onclick={(e) => e.stopPropagation()} role="menu">
                  <button
                    class="bc-export-item"
                    onclick={(e) => pickFormat(e, 'json')}
                    role="menuitem">JSON</button
                  >
                  <button
                    class="bc-export-item"
                    onclick={(e) => pickFormat(e, 'png')}
                    role="menuitem">PNG</button
                  >
                </div>
              {/if}
            </div>
          {/if}
          {#if ondelete}
            <button
              class="bc-action-btn danger"
              onclick={(e) => {
                e.stopPropagation();
                ondelete(bot);
              }}
              title={t('common.delete', lang)}
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
          {/if}
        </div>
      {:else}
        <span class="bc-chat-link">Чат →</span>
      {/if}
    </div>
  </div>
</div>

<style>
  :root {
    --bc-bg-card: #ffffff;
    --bc-border: rgba(0, 0, 0, 0.06);
    --bc-border-strong: rgba(0, 0, 0, 0.1);
    --bc-border-subtle: rgba(0, 0, 0, 0.04);
    --bc-text: #1d1d1f;
    --bc-text-secondary: #6e6e73;
    --bc-text-tertiary: #86868b;
    --bc-shadow-ring: rgba(0, 0, 0, 0.04);
    --bc-shadow-inset: rgba(0, 0, 0, 0.02);
    --bc-blue: hsl(211, 100%, 50%);
    --bc-red: #ff3b30;
    --bc-hover: rgba(0, 0, 0, 0.03);
  }
  :root.dark {
    --bc-bg-card: #101111;
    --bc-border: rgba(255, 255, 255, 0.06);
    --bc-border-strong: rgba(255, 255, 255, 0.1);
    --bc-border-subtle: rgba(255, 255, 255, 0.04);
    --bc-text: #f9f9f9;
    --bc-text-secondary: #9c9c9d;
    --bc-text-tertiary: #6a6b6c;
    --bc-shadow-ring: rgb(27, 28, 30);
    --bc-shadow-inset: rgb(7, 8, 10);
    --bc-blue: hsl(202, 100%, 67%);
    --bc-red: #ff6363;
    --bc-hover: rgba(255, 255, 255, 0.03);
  }

  .bc-card {
    background: var(--bc-bg-card);
    border: 1px solid var(--bc-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow:
      var(--bc-shadow-ring) 0px 0px 0px 1px,
      var(--bc-shadow-inset) 0px 0px 0px 1px inset;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    outline: none;
  }
  .bc-card.bc-clickable {
    cursor: pointer;
  }
  .bc-card:hover {
    border-color: var(--bc-border-strong);
    box-shadow:
      var(--bc-shadow-ring) 0px 0px 0px 1px,
      var(--bc-shadow-inset) 0px 0px 0px 1px inset,
      0 8px 24px color-mix(in srgb, #000 8%, transparent);
    transform: translateY(-1px);
  }
  .bc-hero {
    position: relative;
    width: 100%;
    height: 330px;
    /*overflow: hidden;*/
    background: color-mix(in srgb, var(--bc-text) 3%, transparent);
  }
  .bc-hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }
  .bc-card:hover .bc-hero-img {
    transform: scale(1.03);
  }
  .bc-hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .bc-hero-overlay {
    position: absolute;
    bottom: -10px;
    left: 0;
    right: 0;
    height: 60%;
    background: linear-gradient(to top, var(--bc-bg-card) 20%, transparent);
    pointer-events: none;
  }
  .bc-hero-cats {
    position: absolute;
    top: 8px;
    left: 10px;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .bc-hero-cat {
    font-family: 'Maple Mono', sans-serif;
    font-size: 9px;
    font-weight: 500;
    padding: 2px 7px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--bc-bg-card) 75%, transparent);
    backdrop-filter: blur(8px);
    color: var(--bc-text-secondary);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .bc-hero-type {
    position: absolute;
    top: 8px;
    right: 10px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--bc-bg-card) 75%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .bc-hero-type.rp {
    color: var(--bc-blue);
  }
  .bc-hero-type.assistant {
    color: #5fc992;
  }
  .bc-hero-type.agent {
    color: #f59e0b;
  }
  .bc-hero-name {
    position: absolute;
    bottom: 10px;
    left: 12px;
    right: 12px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--bc-text);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bc-body {
    padding: 12px 14px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
  }
  .bc-desc {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--bc-text-secondary);
    letter-spacing: 0.15px;
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    flex: 1;
  }
  .bc-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 8px;
    border-top: 1px solid var(--bc-border-subtle);
    gap: 8px;
  }
  .bc-threads {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--bc-text-tertiary);
    letter-spacing: 0.2px;
  }
  .bc-chat-link {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--bc-blue);
    letter-spacing: 0.2px;
  }

  .bc-actions {
    display: flex;
    gap: 2px;
  }
  .bc-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--bc-text-secondary);
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .bc-action-btn:hover {
    background: var(--bc-hover);
    color: var(--bc-text);
  }
  .bc-action-btn.chat {
    color: var(--bc-blue);
  }
  .bc-action-btn.chat:hover {
    background: color-mix(in srgb, var(--bc-blue) 10%, transparent);
  }
  .bc-action-btn.danger:hover {
    background: color-mix(in srgb, var(--bc-red) 10%, transparent);
    color: var(--bc-red);
  }

  /* Export dropdown */
  .bc-export-wrap {
    position: relative;
    display: inline-flex;
  }
  .bc-export-menu {
    position: absolute;
    right: 0;
    bottom: calc(100% + 4px);
    background: var(--bc-bg-card);
    border: 1px solid var(--bc-border);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    display: flex;
    flex-direction: column;
    min-width: 80px;
    overflow: hidden;
    z-index: 20;
  }
  .bc-export-item {
    padding: 6px 10px;
    background: transparent;
    border: 0;
    text-align: left;
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    color: var(--bc-text);
    cursor: pointer;
  }
  .bc-export-item:hover {
    background: var(--bc-hover);
  }
</style>
