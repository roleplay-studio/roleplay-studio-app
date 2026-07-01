<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, type Bot } from '../api';
  import BotCard from '../BotCard.svelte';
  import { currentLang, t } from '../i18n';
  import { Input, Loading } from '../ui';

  let lang = $state('en');
  let unsubLang: (() => void) | undefined;
  let bots: Bot[] = $state([]);
  let allCategories: string[] = $state([]);
  let searchQuery = $state('');
  let categoryFilter = $state('');
  let loading = $state(true);

  const filteredBots = $derived(
    bots.filter((b) => {
      if (
        searchQuery &&
        !b.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !b.personality.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !b.scenario.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !b.categories.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase()))
      )
        return false;
      if (categoryFilter && !b.categories.includes(categoryFilter)) return false;
      return true;
    }),
  );

  onMount(async () => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    try {
      [bots, allCategories] = await Promise.all([api.listBots(), api.categories()]);
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    unsubLang?.();
  });

  function navigateToBot(bot: Bot) {
    window.location.hash = `/bot/${bot.id}`;
  }
</script>

<div class="dash-page">
  <!-- Header -->
  <header class="dash-header">
    <div class="dash-header-top">
      <div>
        <h1 class="dash-title">{t('dashboard.title', lang)}</h1>
        <p class="dash-subtitle">{t('dashboard.subtitle', lang)}</p>
      </div>
      <div class="dash-search">
        <svg
          class="dash-search-icon"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"
          ></line></svg
        >
        <Input bind:value={searchQuery} placeholder={t('dashboard.search_placeholder', lang)} />
      </div>
    </div>

    <!-- Category filter pills -->
    {#if allCategories.length > 0}
      <div class="dash-filters">
        <button
          class="dash-filter-pill"
          class:active={categoryFilter === ''}
          onclick={() => (categoryFilter = '')}>{t('dashboard.filter_all', lang)}</button
        >
        {#each allCategories as cat (cat)}
          <button
            class="dash-filter-pill"
            class:active={categoryFilter === cat}
            onclick={() => (categoryFilter = categoryFilter === cat ? '' : cat)}>{cat}</button
          >
        {/each}
      </div>
    {/if}
  </header>

  <!-- Content -->
  {#if loading}
    <div class="dash-loading"><Loading size="lg" /></div>
  {:else if filteredBots.length === 0}
    <div class="dash-empty">
      <svg class="dash-empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1"
          d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <p class="dash-empty-title">{t('dashboard.no_bots', lang)}</p>
      <p class="dash-empty-hint">{t('dashboard.no_bots_hint', lang)}</p>
    </div>
  {:else}
    <div class="dash-grid">
      {#each filteredBots as bot (bot.id)}
        <BotCard {bot} onclick={navigateToBot} />
      {/each}
    </div>
  {/if}
</div>

<style>
  :root {
    --dash-bg-card: #ffffff;
    --dash-border: rgba(0, 0, 0, 0.06);
    --dash-border-strong: rgba(0, 0, 0, 0.1);
    --dash-border-subtle: rgba(0, 0, 0, 0.04);
    --dash-text: #1d1d1f;
    --dash-text-secondary: #6e6e73;
    --dash-text-tertiary: #86868b;
    --dash-shadow-ring: rgba(0, 0, 0, 0.04);
    --dash-shadow-inset: rgba(0, 0, 0, 0.02);
    --dash-blue: hsl(211, 100%, 50%);
    --dash-surface-raised: #f0f0f2;
    --dash-bg: #f5f5f7;
  }
  :root.dark {
    --dash-bg-card: #101111;
    --dash-border: rgba(255, 255, 255, 0.06);
    --dash-border-strong: rgba(255, 255, 255, 0.1);
    --dash-border-subtle: rgba(255, 255, 255, 0.04);
    --dash-text: #f9f9f9;
    --dash-text-secondary: #9c9c9d;
    --dash-text-tertiary: #6a6b6c;
    --dash-shadow-ring: rgb(27, 28, 30);
    --dash-shadow-inset: rgb(7, 8, 10);
    --dash-blue: hsl(202, 100%, 67%);
    --dash-surface-raised: #1b1c1e;
    --dash-bg: #07080a;
  }

  .dash-page {
    padding: 24px 32px;
    color: var(--dash-text);
  }

  /* ─── Header ─── */
  .dash-header {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 28px;
  }
  .dash-header-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .dash-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 24px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--dash-text);
  }
  .dash-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--dash-text-secondary);
    margin: 4px 0 0;
  }
  .dash-search {
    position: relative;
    width: 240px;
  }
  .dash-search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--dash-text-tertiary);
    pointer-events: none;
    z-index: 1;
  }
  :global(.dash-search .ri-field) {
    padding-left: 36px !important;
  }

  /* ─── Filters ─── */
  .dash-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .dash-filter-pill {
    padding: 5px 14px;
    border-radius: 86px;
    border: 1px solid var(--dash-border);
    background: transparent;
    color: var(--dash-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .dash-filter-pill:hover {
    border-color: var(--dash-border-strong);
    color: var(--dash-text);
  }
  .dash-filter-pill.active {
    background: color-mix(in srgb, var(--dash-blue) 12%, transparent);
    border-color: color-mix(in srgb, var(--dash-blue) 30%, transparent);
    color: var(--dash-blue);
  }

  /* ─── Loading / Empty ─── */
  .dash-loading {
    display: flex;
    justify-content: center;
    padding: 80px 0;
  }
  .dash-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 80px 20px;
    background: var(--dash-bg-card);
    border: 1px solid var(--dash-border);
    border-radius: 12px;
    box-shadow:
      var(--dash-shadow-ring) 0px 0px 0px 1px,
      var(--dash-shadow-inset) 0px 0px 0px 1px inset;
  }
  .dash-empty-icon {
    width: 48px;
    height: 48px;
    color: var(--dash-text-tertiary);
    margin-bottom: 16px;
  }
  .dash-empty-title {
    font-size: 16px;
    font-weight: 500;
    color: var(--dash-text-secondary);
    margin-bottom: 4px;
    font-family: 'Maple Mono', sans-serif;
  }
  .dash-empty-hint {
    font-size: 13px;
    color: var(--dash-text-tertiary);
    font-family: 'Maple Mono', sans-serif;
  }

  /* ─── Grid ─── */
  .dash-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }

  /* ─── Card ─── */
  .dash-card {
    background: var(--dash-bg-card);
    border: 1px solid var(--dash-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow:
      var(--dash-shadow-ring) 0px 0px 0px 1px,
      var(--dash-shadow-inset) 0px 0px 0px 1px inset;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
  }
  .dash-card:hover {
    border-color: var(--dash-border-strong);
    box-shadow:
      var(--dash-shadow-ring) 0px 0px 0px 1px,
      var(--dash-shadow-inset) 0px 0px 0px 1px inset,
      0 8px 24px color-mix(in srgb, #000 8%, transparent);
    transform: translateY(-1px);
  }

  /* ─── Hero ─── */
  .dash-hero {
    position: relative;
    width: 100%;
    height: 140px;
    overflow: hidden;
    background: color-mix(in srgb, var(--dash-text) 3%, transparent);
  }
  .dash-hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }
  .dash-card:hover .dash-hero-img {
    transform: scale(1.03);
  }
  .dash-hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 56px;
    font-weight: 700;
    color: #fff;
  }
  .dash-hero-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60%;
    background: linear-gradient(to top, var(--dash-bg-card) 20%, transparent);
    pointer-events: none;
  }
  .dash-hero-cats {
    position: absolute;
    top: 10px;
    left: 10px;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .dash-hero-cat {
    font-family: 'Maple Mono', sans-serif;
    font-size: 10px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--dash-bg-card) 75%, transparent);
    backdrop-filter: blur(8px);
    color: var(--dash-text-secondary);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .dash-hero-type {
    position: absolute;
    top: 10px;
    right: 10px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--dash-bg-card) 75%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
  }
  .dash-hero-type.rp {
    color: var(--dash-blue);
  }
  .dash-hero-type.assistant {
    color: #5fc992;
  }
  .dash-hero-type.agent {
    color: #f59e0b;
  }
  .dash-hero-name {
    position: absolute;
    bottom: 12px;
    left: 14px;
    right: 14px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--dash-text);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ─── Body ─── */
  .dash-body {
    padding: 14px 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
  }
  .dash-desc {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--dash-text-secondary);
    letter-spacing: 0.15px;
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    flex: 1;
  }
  .dash-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px solid var(--dash-border-subtle);
  }
  .dash-threads {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--dash-text-tertiary);
    letter-spacing: 0.2px;
  }
  .dash-chat {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--dash-blue);
    letter-spacing: 0.2px;
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .dash-page {
      padding: 16px;
    }
    .dash-header-top {
      flex-direction: column;
    }
    .dash-search {
      width: 100%;
    }
    .dash-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
