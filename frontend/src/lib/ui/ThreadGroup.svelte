<!-- ThreadGroup — collapsible section header for the cross-bot recent
     chats listing. Renders bot info (avatar + name + categories),
     thread count, last-activity timestamp, and a chevron that rotates
     180° when collapsed. The actual thread rows are passed in via
     a ``children`` snippet so callers stay in charge of row
     rendering.

     Designed to be sticky at the top of the scroll container so the
     user always knows which bot they're looking at as they scroll
     long lists. State (collapsed / expanded) is owned by the parent
     and persisted separately (RecentChats uses localStorage).

     Visual treatment: glass blur on the sticky header keeps the
     sections legible when scrolling over the row below.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';

  const {
    bot_avatar_path,
    bot_categories = [],
    bot_name,
    children,
    isCollapsed,
    lastActivityLabel,
    onToggle,
    threadCount,
  }: {
    bot_avatar_path: null | string;
    bot_categories?: string[];
    bot_name: string;
    children?: Snippet;
    isCollapsed: boolean;
    lastActivityLabel: string;
    onToggle: () => void;
    threadCount: number;
  } = $props();
</script>

<header
  class="tg"
  class:tg-collapsed={isCollapsed}
  role="region"
  aria-label={bot_name}
>
  <button
    type="button"
    class="tg-toggle"
    aria-expanded={!isCollapsed}
    onclick={onToggle}
  >
    <!-- Bot avatar: prefer the uploaded one, fall back to
         GeneratedAvatar block (matches RecentChats' prior visual
         treatment, so the row stays familiar). -->
    {#if bot_avatar_path}
      <img src={bot_avatar_path} alt="" class="tg-avatar tg-avatar-img" />
    {:else}
      <div class="tg-avatar tg-avatar-placeholder">{bot_name.charAt(0).toUpperCase()}</div>
    {/if}

    <div class="tg-info">
      <div class="tg-name-row">
        <span class="tg-name">{bot_name}</span>
        {#if bot_categories.length > 0}
          <span class="tg-cat">{bot_categories[0]}</span>
        {/if}
        <span class="tg-count">{threadCount}</span>
      </div>
      <div class="tg-meta">
        <span class="tg-activity">{lastActivityLabel}</span>
      </div>
    </div>

    <!-- Chevron rotates 180° when collapsed; transform-only
         animation so we don't repaint the avatar/text on toggle. -->
    <svg
      class="tg-chevron"
      class:tg-chevron-collapsed={isCollapsed}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if !isCollapsed && children}
    <div class="tg-body">
      {@render children()}
    </div>
  {/if}
</header>

<style>
  .tg {
    /* Sticky so the group header stays visible while the user
       scrolls through long thread lists. backdrop-blur gives the
       glass effect that masks the rows below. */
    position: sticky;
    top: 0;
    z-index: 2;
    background: color-mix(in srgb, var(--tg-bg, #ffffff) 92%, transparent);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--tg-border-subtle, rgba(0, 0, 0, 0.04));
  }
  :global(.dark) .tg {
    background: color-mix(in srgb, var(--tg-surface, #101111) 92%, transparent);
  }

  .tg-toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 12px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: inherit;
    font: inherit;
    text-align: left;
    transition: background 0.12s ease;
  }
  .tg-toggle:hover {
    background: var(--tg-hover, rgba(0, 0, 0, 0.03));
  }
  .tg-toggle:focus-visible {
    outline: none;
    background: var(--tg-hover, rgba(0, 0, 0, 0.03));
    box-shadow: inset 0 0 0 2px color-mix(in srgb, hsl(202, 100%, 67%) 30%, transparent);
  }

  .tg-avatar {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    overflow: hidden;
    flex-shrink: 0;
    background: var(--tg-bg, #ffffff);
  }
  .tg-avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .tg-avatar-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Maple Mono', monospace;
    font-size: 16px;
    font-weight: 600;
    color: var(--tg-text-secondary, #6e6e73);
    background: color-mix(in srgb, var(--tg-text, #1d1d1f) 6%, transparent);
  }

  .tg-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .tg-name-row {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .tg-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--tg-text, #1d1d1f);
    letter-spacing: 0.2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 0 1 auto;
    min-width: 0;
  }
  .tg-cat {
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    padding: 1px 7px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--tg-text, #1d1d1f) 5%, transparent);
    color: var(--tg-text-secondary, #6e6e73);
    letter-spacing: 0.3px;
    flex-shrink: 0;
  }
  /* Thread count — small pill, monochrome. Mirrors the recent-row
     count badge styling in RecentChats so the eye tracks them
     as the same UI primitive. */
  .tg-count {
    flex-shrink: 0;
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    color: var(--tg-text-secondary, #6e6e73);
    background: color-mix(in srgb, var(--tg-text, #1d1d1f) 6%, transparent);
    padding: 1px 6px;
    border-radius: 86px;
    font-feature-settings: 'tnum' 1;
    letter-spacing: 0.2px;
    margin-left: auto;
  }

  .tg-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--tg-text-tertiary, #86868b);
  }
  .tg-activity {
    letter-spacing: 0.2px;
  }

  .tg-chevron {
    color: var(--tg-text-tertiary, #86868b);
    flex-shrink: 0;
    transform: rotate(0deg);
    transition: transform 0.15s ease, color 0.12s ease;
  }
  .tg-chevron-collapsed {
    transform: rotate(-90deg);
  }
  .tg:hover .tg-chevron {
    color: var(--tg-text-secondary, #6e6e73);
  }

  /* Body section — relative+lower z-index so the sticky header
     floats above the rows; each row gets a subtle top padding so
     the sticky header doesn't visually clip the first row. */
  .tg-body {
    position: relative;
    z-index: 1;
    padding-top: 2px;
    background: var(--tg-bg, #ffffff);
  }
</style>
